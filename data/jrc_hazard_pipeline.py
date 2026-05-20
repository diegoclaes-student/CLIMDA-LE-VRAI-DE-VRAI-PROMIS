from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import os
import json
import math
import urllib.request

import numpy as np
import pandas as pd


# =============================================================================
# JRC Copernicus flood hazard pipeline (Belgium)
# - Reproject JRC GeoTIFFs to EPSG:31370 (Lambert 72) on-the-fly
# - Mask permanent water bodies + depth threshold
# - Zonal stats for provinces, communes, basins
# - Export sparse hazard matrix for CLIMADA (centroids)
# =============================================================================


JRC_RP_FILES = {
    10:  "Europe_RP10_filled_depth.tif",
    50:  "Europe_RP50_filled_depth.tif",
    100: "Europe_RP100_filled_depth.tif",
    200: "Europe_RP200_filled_depth.tif",
    500: "Europe_RP500_filled_depth.tif",
}

PERMANENT_WATER_FILE = "Europe_permanent_water_bodies.tif"

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
DEFAULT_INPUT_DIR = os.path.join(PROJECT_ROOT, "data", "jrc_inputs")
DEFAULT_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs_generated", "jrc_hazard")
DEFAULT_CACHE_DIR = os.path.join(PROJECT_ROOT, "outputs_generated", "cache")

GADM_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/shp/gadm41_BEL_shp.zip"
HYDROBASINS_EU_L6_URL = (
    "https://data.hydrosheds.org/file/hydrobasins/standard/hybas_eu_lev06_v1c.zip"
)


@dataclass
class JrcHazardConfig:
    input_dir: str = DEFAULT_INPUT_DIR
    output_dir: str = DEFAULT_OUTPUT_DIR
    cache_dir: str = DEFAULT_CACHE_DIR
    target_crs: str = "EPSG:31370"
    depth_threshold_m: float = 0.05
    water_mask_threshold: float = 0.5
    rp_files: dict[int, str] = field(default_factory=lambda: dict(JRC_RP_FILES))
    permanent_water_file: str = PERMANENT_WATER_FILE
    window_size: int = 1024
    export_hazard_matrix: bool = True
    hazard_matrix_format: str = "parquet"
    export_hazard_json: bool = False
    write_cleaned_rasters: bool = False
    cleaned_raster_dir: Optional[str] = None
    allow_csv_fallback: bool = False
    basin_polygons_path: Optional[str] = None
    basin_name_field: Optional[str] = None
    auto_download_basins: bool = True


def _require_rasterio():
    try:
        import rasterio  # noqa: F401
        from rasterio.vrt import WarpedVRT  # noqa: F401
        from rasterio.enums import Resampling  # noqa: F401
        from rasterio.features import rasterize  # noqa: F401
        from rasterio.warp import calculate_default_transform  # noqa: F401
        from rasterio.warp import transform as warp_transform  # noqa: F401
        from rasterio.windows import Window  # noqa: F401
        from rasterio.windows import bounds as window_bounds  # noqa: F401
        from rasterio.windows import transform as window_transform  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "rasterio is required for the JRC hazard pipeline. "
            "Install with: pip install rasterio"
        ) from exc


def _require_geopandas():
    try:
        import geopandas  # noqa: F401
        from shapely.geometry import box  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "geopandas (and shapely) are required for the JRC hazard pipeline. "
            "Install with: pip install geopandas shapely"
        ) from exc


def _download_with_cache(url: str, dest_path: str) -> str:
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    if not os.path.exists(dest_path):
        print(f"  [download] {url}")
        urllib.request.urlretrieve(url, dest_path)
    return dest_path


def _validate_input_files(cfg: JrcHazardConfig) -> tuple[dict[int, str], str]:
    missing = []
    rp_paths = {}
    for rp, fname in cfg.rp_files.items():
        path = os.path.join(cfg.input_dir, fname)
        if not os.path.exists(path):
            missing.append(path)
        rp_paths[rp] = path

    mask_path = os.path.join(cfg.input_dir, cfg.permanent_water_file)
    if not os.path.exists(mask_path):
        missing.append(mask_path)

    if missing:
        msg = "Missing input files:\n" + "\n".join(f"  - {p}" for p in missing)
        raise FileNotFoundError(msg)

    return rp_paths, mask_path


def _load_admin_boundaries(cfg: JrcHazardConfig, target_crs: str):
    _require_geopandas()
    import geopandas as gpd

    zip_path = _download_with_cache(GADM_URL, os.path.join(cfg.cache_dir, "gadm41_BEL_shp.zip"))
    prov_path = f"zip://{zip_path}!gadm41_BEL_1.shp"
    comm_path = f"zip://{zip_path}!gadm41_BEL_3.shp"

    provinces = gpd.read_file(prov_path)
    communes = gpd.read_file(comm_path)

    required_prov_cols = {"GID_1", "NAME_1"}
    required_comm_cols = {"GID_3", "NAME_3"}
    if not required_prov_cols.issubset(set(provinces.columns)):
        raise ValueError(f"GADM provinces missing columns: {required_prov_cols}")
    if not required_comm_cols.issubset(set(communes.columns)):
        raise ValueError(f"GADM communes missing columns: {required_comm_cols}")

    provinces = provinces.to_crs(target_crs)
    communes = communes.to_crs(target_crs)

    provinces = provinces[["GID_1", "NAME_1", "geometry"]].copy()
    communes = communes[["GID_3", "NAME_3", "geometry"]].copy()

    provinces.rename(columns={"GID_1": "zone_id", "NAME_1": "zone_name"}, inplace=True)
    communes.rename(columns={"GID_3": "zone_id", "NAME_3": "zone_name"}, inplace=True)

    return provinces, communes


def _infer_basin_name_field(columns: list[str]) -> Optional[str]:
    candidates = ["NAME", "BASIN_NAME", "NAME_EN", "RBD_NAME", "NAME_1"]
    for c in candidates:
        if c in columns:
            return c
    return None


def _load_basin_boundaries(cfg: JrcHazardConfig, target_crs: str):
    _require_geopandas()
    import geopandas as gpd

    basin_path = cfg.basin_polygons_path
    if basin_path is None and cfg.auto_download_basins:
        zip_path = _download_with_cache(
            HYDROBASINS_EU_L6_URL,
            os.path.join(cfg.cache_dir, "hybas_eu_lev06_v1c.zip"),
        )
        basin_path = f"zip://{zip_path}!hybas_eu_lev06_v1c.shp"

    if basin_path is None:
        return None

    basins = gpd.read_file(basin_path)
    if basins.empty:
        raise ValueError("Basin polygons file is empty.")

    name_field = cfg.basin_name_field or _infer_basin_name_field(list(basins.columns))
    if name_field is None:
        raise ValueError(
            "Unable to infer basin name field. Provide basin_name_field in config."
        )

    basins = basins.to_crs(target_crs)
    name_series = basins[name_field].astype(str).str.lower()

    meuse_mask = name_series.str.contains("meuse|maas", regex=True)
    escaut_mask = name_series.str.contains("escaut|scheldt|schelde", regex=True)

    if not meuse_mask.any() or not escaut_mask.any():
        raise ValueError(
            "Basin polygons do not contain Meuse/Escaut names. "
            "Provide a basin dataset with recognizable names."
        )

    meuse_geom = basins.loc[meuse_mask, "geometry"].unary_union
    escaut_geom = basins.loc[escaut_mask, "geometry"].unary_union

    basins_out = gpd.GeoDataFrame(
        {
            "zone_id": ["Meuse", "Escaut"],
            "zone_name": ["Meuse", "Escaut"],
            "geometry": [meuse_geom, escaut_geom],
        },
        crs=target_crs,
    )
    return basins_out


def _window_iter(width: int, height: int, window_size: int):
    from rasterio.windows import Window

    for row in range(0, height, window_size):
        for col in range(0, width, window_size):
            w = min(window_size, width - col)
            h = min(window_size, height - row)
            yield Window(col, row, w, h)


def _prepare_zone_set(gdf, zone_type: str):
    gdf = gdf.copy()
    gdf["zone_idx"] = np.arange(1, len(gdf) + 1, dtype=np.int32)
    gdf["area_m2"] = gdf.geometry.area.astype(float)
    gdf.reset_index(drop=True, inplace=True)
    gdf.sindex  # build spatial index
    return {
        "type": zone_type,
        "gdf": gdf,
        "zone_ids": gdf["zone_id"].tolist(),
        "zone_names": gdf["zone_name"].tolist(),
        "area_m2": gdf["area_m2"].to_numpy(dtype=float),
        "n_zones": len(gdf),
    }


def _rasterize_zones(zone_set, window_bounds, window_transform, out_shape):
    _require_geopandas()
    from shapely.geometry import box
    from rasterio.features import rasterize

    gdf = zone_set["gdf"]
    if gdf.empty:
        return np.zeros(out_shape, dtype=np.int32)

    idx = list(gdf.sindex.intersection(window_bounds))
    if not idx:
        return np.zeros(out_shape, dtype=np.int32)

    window_geom = box(*window_bounds)
    subset = gdf.iloc[idx]
    subset = subset[subset.intersects(window_geom)]
    if subset.empty:
        return np.zeros(out_shape, dtype=np.int32)

    shapes = ((geom, int(zone_idx)) for geom, zone_idx in zip(subset.geometry, subset["zone_idx"]))
    return rasterize(
        shapes=shapes,
        out_shape=out_shape,
        transform=window_transform,
        fill=0,
        dtype="int32",
    )


def _init_stats(n_zones: int):
    return {
        "flood_area_m2": np.zeros(n_zones + 1, dtype=float),
        "depth_sum_m3": np.zeros(n_zones + 1, dtype=float),
        "max_depth_m": np.zeros(n_zones + 1, dtype=float),
    }


def _update_zone_stats(zone_set, stats, window_transform, window_bounds, depth, valid_mask, pixel_area):
    if not valid_mask.any():
        return

    zone_ids = _rasterize_zones(zone_set, window_bounds, window_transform, depth.shape)
    zone_ids = zone_ids[valid_mask]
    if zone_ids.size == 0:
        return

    depth_valid = depth[valid_mask]
    area_weights = np.full_like(depth_valid, pixel_area, dtype=float)
    stats["flood_area_m2"] += np.bincount(
        zone_ids, weights=area_weights, minlength=zone_set["n_zones"] + 1
    )
    stats["depth_sum_m3"] += np.bincount(
        zone_ids, weights=depth_valid * pixel_area, minlength=zone_set["n_zones"] + 1
    )
    np.maximum.at(stats["max_depth_m"], zone_ids, depth_valid)


def _stats_to_dataframe(zone_set, stats, rp_years: int):
    area = zone_set["area_m2"]
    flood_area = stats["flood_area_m2"][1:]
    depth_sum = stats["depth_sum_m3"][1:]
    max_depth = stats["max_depth_m"][1:]

    mean_depth = np.where(flood_area > 0, depth_sum / flood_area, np.nan)
    flood_pct = np.where(area > 0, flood_area / area * 100.0, np.nan)
    max_depth = np.where(flood_area > 0, max_depth, np.nan)

    return pd.DataFrame(
        {
            "zone_type": zone_set["type"],
            "zone_id": zone_set["zone_ids"],
            "zone_name": zone_set["zone_names"],
            "rp_years": rp_years,
            "zone_area_km2": area / 1e6,
            "flood_area_km2": flood_area / 1e6,
            "flood_pct": flood_pct,
            "mean_depth_m": mean_depth,
            "max_depth_m": max_depth,
        }
    )


class HazardMatrixWriter:
    def __init__(
        self,
        path: str,
        fmt: str,
        allow_csv_fallback: bool = False,
        json_path: Optional[str] = None,
    ):
        self.path = path
        self.format = fmt.lower()
        self.json_path = json_path
        self.allow_csv_fallback = allow_csv_fallback
        self._buffer = []
        self._writer = None
        self._json_handle = None

        if self.format not in {"parquet", "csv"}:
            raise ValueError("hazard_matrix_format must be 'parquet' or 'csv'")

        if self.format == "parquet":
            try:
                import pyarrow as pa  # noqa: F401
                import pyarrow.parquet as pq  # noqa: F401
            except ImportError as exc:
                if self.allow_csv_fallback:
                    self.format = "csv"
                else:
                    raise ImportError(
                        "pyarrow is required to write Parquet. "
                        "Install with: pip install pyarrow"
                    ) from exc

    def _open_writer(self, df: pd.DataFrame):
        if self.format == "parquet":
            import pyarrow as pa
            import pyarrow.parquet as pq

            table = pa.Table.from_pandas(df, preserve_index=False)
            self._writer = pq.ParquetWriter(self.path, table.schema)
        else:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            df.head(0).to_csv(self.path, index=False)

        if self.json_path:
            os.makedirs(os.path.dirname(self.json_path), exist_ok=True)
            self._json_handle = open(self.json_path, "w", encoding="utf-8")

    def append(self, df: pd.DataFrame):
        if df.empty:
            return
        if self._writer is None:
            self._open_writer(df)

        if self.format == "parquet":
            import pyarrow as pa

            table = pa.Table.from_pandas(df, preserve_index=False)
            self._writer.write_table(table)
        else:
            df.to_csv(self.path, mode="a", header=False, index=False)

        if self._json_handle is not None:
            for record in df.to_dict(orient="records"):
                self._json_handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    def close(self):
        if self._writer is not None and self.format == "parquet":
            self._writer.close()
        if self._json_handle is not None:
            self._json_handle.close()


def _compute_target_grid(raster_path: str, target_crs: str, bounds_target):
    _require_rasterio()
    import rasterio
    from rasterio.warp import calculate_default_transform
    from rasterio.transform import from_origin

    with rasterio.open(raster_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, target_crs, src.width, src.height, *src.bounds
        )
        res_x = transform.a
        res_y = abs(transform.e)

    minx, miny, maxx, maxy = bounds_target
    width = int(math.ceil((maxx - minx) / res_x))
    height = int(math.ceil((maxy - miny) / res_y))
    transform = from_origin(minx, maxy, res_x, res_y)
    return transform, width, height


def _open_warped(raster_path: str, target_crs: str, transform, width, height, resampling):
    _require_rasterio()
    import rasterio
    from rasterio.vrt import WarpedVRT

    src = rasterio.open(raster_path)
    vrt = WarpedVRT(
        src,
        crs=target_crs,
        transform=transform,
        width=width,
        height=height,
        resampling=resampling,
    )
    return src, vrt


def _prepare_output_dirs(cfg: JrcHazardConfig):
    os.makedirs(cfg.output_dir, exist_ok=True)
    os.makedirs(cfg.cache_dir, exist_ok=True)
    if cfg.write_cleaned_rasters:
        cleaned_dir = cfg.cleaned_raster_dir or os.path.join(cfg.output_dir, "cleaned_rasters")
        os.makedirs(cleaned_dir, exist_ok=True)


def _compute_basin_stats_from_provinces(prov_df: pd.DataFrame):
    from data.historical_belgium import RIVER_BASINS

    mapping = {}
    for basin_name, data in RIVER_BASINS.items():
        if basin_name not in {"Meuse", "Escaut"}:
            continue
        mapping[basin_name] = set(data["provinces"])

    rows = []
    for basin_name, prov_set in mapping.items():
        sub = prov_df[prov_df["zone_name"].isin(prov_set)]
        if sub.empty:
            continue
        flood_area = sub["flood_area_km2"].sum()
        zone_area = sub["zone_area_km2"].sum()
        depth_sum = (sub["mean_depth_m"] * sub["flood_area_km2"]).sum()
        mean_depth = depth_sum / flood_area if flood_area > 0 else np.nan
        max_depth = sub["max_depth_m"].max()
        flood_pct = (flood_area / zone_area * 100.0) if zone_area > 0 else np.nan
        rows.append(
            {
                "zone_type": "basin",
                "zone_id": basin_name,
                "zone_name": basin_name,
                "rp_years": int(sub["rp_years"].iloc[0]),
                "zone_area_km2": zone_area,
                "flood_area_km2": flood_area,
                "flood_pct": flood_pct,
                "mean_depth_m": mean_depth,
                "max_depth_m": max_depth,
                "source": "province_mapping",
            }
        )
    return pd.DataFrame(rows)


def run_jrc_pipeline(cfg: Optional[JrcHazardConfig] = None) -> dict:
    _require_rasterio()
    _require_geopandas()
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.windows import bounds as window_bounds
    from rasterio.windows import transform as window_transform
    from rasterio.warp import transform as warp_transform

    if cfg is None:
        cfg = JrcHazardConfig()

    _prepare_output_dirs(cfg)
    rp_paths, mask_path = _validate_input_files(cfg)

    print("\n--- JRC Hazard Pipeline (Belgium) ---")
    print(f"  Input dir  : {cfg.input_dir}")
    print(f"  Output dir : {cfg.output_dir}")
    print(f"  CRS cible  : {cfg.target_crs}")

    provinces_gdf, communes_gdf = _load_admin_boundaries(cfg, cfg.target_crs)
    basins_gdf = _load_basin_boundaries(cfg, cfg.target_crs)

    province_set = _prepare_zone_set(provinces_gdf, "province")
    commune_set = _prepare_zone_set(communes_gdf, "commune")
    basin_set = _prepare_zone_set(basins_gdf, "basin") if basins_gdf is not None else None

    bounds_target = provinces_gdf.total_bounds
    transform, width, height = _compute_target_grid(
        next(iter(rp_paths.values())), cfg.target_crs, bounds_target
    )
    pixel_area = abs(transform.a * transform.e)

    hazard_path = os.path.join(cfg.output_dir, "hazard_matrix.parquet")
    json_path = os.path.join(cfg.output_dir, "hazard_matrix.jsonl") if cfg.export_hazard_json else None
    writer = None
    if cfg.export_hazard_matrix:
        fmt = cfg.hazard_matrix_format
        if fmt == "parquet":
            hazard_path = os.path.join(cfg.output_dir, "hazard_matrix.parquet")
        else:
            hazard_path = os.path.join(cfg.output_dir, "hazard_matrix.csv")
        writer = HazardMatrixWriter(
            hazard_path, fmt=fmt, allow_csv_fallback=cfg.allow_csv_fallback, json_path=json_path
        )

    stats_outputs = {"provinces": [], "communes": [], "basins": []}

    for rp, raster_path in sorted(rp_paths.items()):
        print(f"  [rp {rp}] processing {os.path.basename(raster_path)}")
        depth_src, depth_vrt = _open_warped(
            raster_path, cfg.target_crs, transform, width, height, Resampling.bilinear
        )
        mask_src, mask_vrt = _open_warped(
            mask_path, cfg.target_crs, transform, width, height, Resampling.nearest
        )

        depth_nodata = depth_src.nodata
        mask_nodata = mask_src.nodata

        cleaned_dst = None
        if cfg.write_cleaned_rasters:
            cleaned_dir = cfg.cleaned_raster_dir or os.path.join(cfg.output_dir, "cleaned_rasters")
            os.makedirs(cleaned_dir, exist_ok=True)
            cleaned_path = os.path.join(cleaned_dir, f"JRC_RP{rp}_cleaned_31370.tif")
            cleaned_profile = {
                "driver": "GTiff",
                "height": height,
                "width": width,
                "count": 1,
                "crs": cfg.target_crs,
                "transform": transform,
                "dtype": "float32",
                "nodata": -9999.0,
                "tiled": True,
                "blockxsize": 256,
                "blockysize": 256,
                "compress": "lzw",
            }
            cleaned_dst = rasterio.open(cleaned_path, "w", **cleaned_profile)

        prov_stats = _init_stats(province_set["n_zones"])
        comm_stats = _init_stats(commune_set["n_zones"])
        basin_stats = _init_stats(basin_set["n_zones"]) if basin_set is not None else None

        for window in _window_iter(width, height, cfg.window_size):
            depth = depth_vrt.read(1, window=window, masked=False).astype(np.float32)
            water = mask_vrt.read(1, window=window, masked=False)

            if depth_nodata is not None:
                depth = np.where(depth == depth_nodata, np.nan, depth)
            if mask_nodata is not None:
                water = np.where(water == mask_nodata, 0, water)

            depth = np.where(water > cfg.water_mask_threshold, np.nan, depth)
            depth = np.where(depth < cfg.depth_threshold_m, np.nan, depth)
            depth = depth.astype(np.float32, copy=False)

            valid = np.isfinite(depth)
            if not valid.any():
                continue

            win_transform = window_transform(window, transform)
            win_bounds = window_bounds(window, transform)

            _update_zone_stats(
                province_set, prov_stats, win_transform, win_bounds, depth, valid, pixel_area
            )
            _update_zone_stats(
                commune_set, comm_stats, win_transform, win_bounds, depth, valid, pixel_area
            )
            if basin_set is not None:
                _update_zone_stats(
                    basin_set, basin_stats, win_transform, win_bounds, depth, valid, pixel_area
                )

            if writer is not None:
                rows, cols = np.where(valid)
                xs, ys = rasterio.transform.xy(win_transform, rows, cols, offset="center")
                lon, lat = warp_transform(cfg.target_crs, "EPSG:4326", xs, ys)
                depth_vals = depth[rows, cols]
                df = pd.DataFrame(
                    {
                        "rp_years": rp,
                        "x_31370": xs,
                        "y_31370": ys,
                        "lon": lon,
                        "lat": lat,
                        "depth_m": depth_vals,
                    }
                )
                writer.append(df)

            if cleaned_dst is not None:
                depth_out = np.where(valid, depth, cleaned_dst.nodata).astype(np.float32)
                cleaned_dst.write(depth_out, 1, window=window)

        depth_vrt.close()
        depth_src.close()
        mask_vrt.close()
        mask_src.close()
        if cleaned_dst is not None:
            cleaned_dst.close()

        prov_df = _stats_to_dataframe(province_set, prov_stats, rp)
        comm_df = _stats_to_dataframe(commune_set, comm_stats, rp)
        stats_outputs["provinces"].append(prov_df)
        stats_outputs["communes"].append(comm_df)

        if basin_set is not None:
            basin_df = _stats_to_dataframe(basin_set, basin_stats, rp)
            basin_df["source"] = "basin_polygons"
        else:
            basin_df = _compute_basin_stats_from_provinces(prov_df)
        stats_outputs["basins"].append(basin_df)

    if writer is not None:
        writer.close()

    provinces_all = pd.concat(stats_outputs["provinces"], ignore_index=True)
    communes_all = pd.concat(stats_outputs["communes"], ignore_index=True)
    basins_all = pd.concat(stats_outputs["basins"], ignore_index=True)

    provinces_path = os.path.join(cfg.output_dir, "stats_provinces.csv")
    communes_path = os.path.join(cfg.output_dir, "stats_communes.csv")
    basins_path = os.path.join(cfg.output_dir, "stats_basins.csv")
    provinces_all.to_csv(provinces_path, index=False)
    communes_all.to_csv(communes_path, index=False)
    basins_all.to_csv(basins_path, index=False)

    top_max = (
        communes_all.sort_values(["rp_years", "max_depth_m"], ascending=[True, False])
        .groupby("rp_years")
        .head(10)
    )
    top_pct = (
        communes_all.sort_values(["rp_years", "flood_pct"], ascending=[True, False])
        .groupby("rp_years")
        .head(10)
    )

    top_max_path = os.path.join(cfg.output_dir, "top10_communes_max_depth.csv")
    top_pct_path = os.path.join(cfg.output_dir, "top10_communes_flood_pct.csv")
    top_max.to_csv(top_max_path, index=False)
    top_pct.to_csv(top_pct_path, index=False)

    basins_source = (
        "user-provided"
        if cfg.basin_polygons_path
        else ("hydrobasins" if cfg.auto_download_basins else "province_mapping")
    )
    meta = {
        "target_crs": cfg.target_crs,
        "depth_threshold_m": cfg.depth_threshold_m,
        "water_mask_threshold": cfg.water_mask_threshold,
        "window_size": cfg.window_size,
        "rp_files": cfg.rp_files,
        "permanent_water_file": cfg.permanent_water_file,
        "hazard_matrix": hazard_path if cfg.export_hazard_matrix else None,
        "hazard_matrix_jsonl": json_path if cfg.export_hazard_json else None,
        "sources": {
            "jrc": "JRC Copernicus flood hazard maps v3.1.1",
            "admin": "GADM 4.1 (BEL)",
            "basins": basins_source,
        },
    }
    meta_path = os.path.join(cfg.output_dir, "pipeline_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=True, indent=2)

    print("  ✓ Stats provinces:", provinces_path)
    print("  ✓ Stats communes :", communes_path)
    print("  ✓ Stats basins   :", basins_path)
    print("  ✓ Top 10 depth   :", top_max_path)
    print("  ✓ Top 10 pct     :", top_pct_path)
    if cfg.export_hazard_matrix:
        print("  ✓ Hazard matrix :", hazard_path)
        if cfg.export_hazard_json:
            print("  ✓ Hazard JSONL  :", json_path)

    return {
        "provinces": provinces_path,
        "communes": communes_path,
        "basins": basins_path,
        "top10_max_depth": top_max_path,
        "top10_flood_pct": top_pct_path,
        "hazard_matrix": hazard_path if cfg.export_hazard_matrix else None,
        "metadata": meta_path,
    }
