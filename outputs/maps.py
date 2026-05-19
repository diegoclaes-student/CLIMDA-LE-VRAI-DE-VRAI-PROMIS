# =============================================================================
# outputs/maps.py  —  VERSION 2 (choroplèthes geopandas, données Natural Earth)
#
# Données géographiques : Natural Earth 10m (naciscdn.org) — licence CC0
# Provinces belges : ne_10m_admin_1_states_provinces (11 entités)
# Rivières         : ne_10m_rivers_lake_centerlines (Maas/Meuse + Schelde)
# Pays voisins     : ne_10m_admin_0_countries (France, NL, DE, LU)
# =============================================================================

import os
import numpy as np
import warnings
warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as mcm
import matplotlib.patches as mpatches
from matplotlib.colors import Normalize, TwoSlopeNorm, BoundaryNorm
import matplotlib.patheffects as pe

import geopandas as gpd

from models.exposure_model import PROVINCES
from models.hazard_model import (
    PROVINCE_HAZARD, get_hazard_index_by_province,
)
from models.exposure_model import get_exposed_value_by_province
from data.rcp_scenarios import SCENARIOS, get_warming_at_year, get_damage_factor

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs_generated", "figures")

# ---------------------------------------------------------------------------
# Correspondance noms Natural Earth → noms du modèle
# Natural Earth utilise les noms anglais des provinces
# ---------------------------------------------------------------------------
NE_TO_MODEL = {
    "West Flanders":   "West-Vlaanderen",
    "East Flanders":   "Oost-Vlaanderen",
    "Antwerp":         "Antwerpen",
    "Limburg":         None,              # Limburg BE absent du modèle (pas de côte/inondation)
    "Flemish Brabant": "Vlaams-Brabant",
    "Brussels":        "Bruxelles",
    "Walloon Brabant": "Brabant Wallon",
    "Hainaut":         "Hainaut",
    "Namur":           "Namur",
    "Liege":           "Liège",
    "Luxembourg":      "Luxembourg",
}

# Province de Limbourg — données de modélisation
# (non dans notre modèle car faible risque d'inondation fluviale)
LIMBURG_DATA = {
    "freq_events_per_decade": 0.5,
    "gdp_BEUR": 22.0,
    "flood_zone_pct_Q100": 6.0,
    "region": "Flandre",
}


# ---------------------------------------------------------------------------
# Chargement et cache des données géographiques
# ---------------------------------------------------------------------------
_GEO_CACHE = {}

def _load_geodata():
    """Charge (et met en cache) toutes les données géographiques."""
    global _GEO_CACHE
    if _GEO_CACHE:
        return _GEO_CACHE

    print("  [geo] Chargement des données Natural Earth (Natural Earth, CC0)...")

    # Provinces belges
    url_prov = "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_1_states_provinces.zip"
    all_prov = gpd.read_file(url_prov)
    be_prov  = all_prov[all_prov["iso_a2"] == "BE"].copy()
    be_prov  = be_prov.to_crs("EPSG:4326")
    print(f"  [geo] Provinces belges : {len(be_prov)} entités chargées")

    # Pays voisins (pour contexte)
    url_ctry = "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip"
    ctry     = gpd.read_file(url_ctry)
    neighbors = ctry[ctry["ADMIN"].isin(
        ["Belgium", "France", "Germany", "Luxembourg", "Netherlands"]
    )].to_crs("EPSG:4326")

    # Rivières (global 10m)
    url_riv  = "https://naciscdn.org/naturalearth/10m/physical/ne_10m_rivers_lake_centerlines.zip"
    all_riv  = gpd.read_file(url_riv)
    # Filtrer Meuse + Escaut dans la bbox belge + tampon
    be_rivers = all_riv.cx[2.0:7.0, 49.0:52.0].copy()
    be_rivers = be_rivers.to_crs("EPSG:4326")
    print(f"  [geo] Rivières dans bbox : {len(be_rivers)} ({list(be_rivers['name'].dropna())})")

    # Rivières européennes (10m) — pour les affluents
    url_riv_eu = "https://naciscdn.org/naturalearth/10m/physical/ne_10m_rivers_europe.zip"
    riv_eu   = gpd.read_file(url_riv_eu)
    be_riv_eu = riv_eu.cx[2.0:7.0, 49.0:52.0].copy().to_crs("EPSG:4326")
    print(f"  [geo] Rivières EU bbox : {len(be_riv_eu)} entités")

    _GEO_CACHE = {
        "be_prov":    be_prov,
        "neighbors":  neighbors,
        "be_rivers":  be_rivers,
        "be_riv_eu":  be_riv_eu,
    }
    return _GEO_CACHE


# ---------------------------------------------------------------------------
# Helper : ajout données au GeoDataFrame provinces
# ---------------------------------------------------------------------------

def _build_province_gdf(value_dict: dict, col_name: str = "value") -> gpd.GeoDataFrame:
    """
    Fusionne un dict {model_name: value} avec le GeoDataFrame des provinces.
    Renvoie un GeoDataFrame avec la colonne 'value'.
    """
    geo = _load_geodata()
    gdf = geo["be_prov"].copy()

    values = []
    for _, row in gdf.iterrows():
        ne_name    = row["name"]
        model_name = NE_TO_MODEL.get(ne_name)
        if model_name and model_name in value_dict:
            values.append(value_dict[model_name])
        elif ne_name == "Limburg":
            # Valeur par défaut pour Limbourg
            values.append(LIMBURG_DATA.get(col_name, 0.5))
        else:
            values.append(np.nan)
    gdf[col_name] = values
    return gdf


def _setup_map_ax(ax, title: str, fontsize: int = 11):
    """Configure un axe pour une carte de Belgique avec pays voisins."""
    ax.set_xlim(2.35, 6.55)
    ax.set_ylim(49.40, 51.60)
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=fontsize, fontweight="bold", pad=5)
    ax.set_xlabel("Longitude (°E)", fontsize=8)
    ax.set_ylabel("Latitude (°N)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(True, alpha=0.25, linewidth=0.4, color="#888888")


def _draw_context(ax, geo: dict, alpha_neighbor: float = 0.12):
    """Dessine les pays voisins en fond gris + ombrage léger."""
    geo["neighbors"].plot(
        ax=ax, color="#e8e8e0", edgecolor="#aaaaaa",
        linewidth=0.6, alpha=alpha_neighbor + 0.8, zorder=1,
    )
    # Rebords pays
    geo["neighbors"].boundary.plot(
        ax=ax, color="#888888", linewidth=0.5, alpha=0.7, zorder=2,
    )


def _draw_rivers(ax, geo: dict):
    """Trace les rivières principales (Maas/Meuse, Schelde) + affluents."""
    # Rivières principales — trait large + bleu profond
    river_names_main = {"Maas", "Schelde"}
    main = geo["be_rivers"][
        geo["be_rivers"]["name"].isin(river_names_main)
    ]
    if len(main) > 0:
        main.plot(ax=ax, color="#1565C0", linewidth=1.8, alpha=0.85, zorder=6)

    # Affluents européens — trait fin
    if len(geo["be_riv_eu"]) > 0:
        geo["be_riv_eu"].plot(
            ax=ax, color="#42A5F5", linewidth=0.9, alpha=0.65, zorder=5,
        )

    # Légende rivières
    main_patch  = mpatches.Patch(color="#1565C0", label="Meuse / Escaut")
    trib_patch  = mpatches.Patch(color="#42A5F5", alpha=0.65, label="Affluents")
    return [main_patch, trib_patch]


def _add_province_labels(ax, gdf: gpd.GeoDataFrame, fontsize: int = 6):
    """Ajoute les noms de provinces au centroïde de chaque province."""
    for _, row in gdf.iterrows():
        ne_name = row["name"]
        model_name = NE_TO_MODEL.get(ne_name, ne_name)
        if model_name is None:
            model_name = "Limburg"
        # Centroïde géographique
        try:
            centroid = row.geometry.centroid
            label = model_name.replace("-", "-\n") if len(model_name) > 12 else model_name
            ax.text(
                centroid.x, centroid.y, label,
                ha="center", va="center",
                fontsize=fontsize, color="#1a1a1a",
                fontweight="bold",
                path_effects=[
                    pe.withStroke(linewidth=2, foreground="white"),
                ],
                zorder=9,
            )
        except Exception:
            pass


def _add_source_fig(fig, text: str, y: float = 0.01):
    fig.text(
        0.5, y, text,
        ha="center", va="bottom", fontsize=5.8,
        style="italic", color="#444444",
    )


# ---------------------------------------------------------------------------
# CARTE A — Évolution temporelle RCP 4.5 (4 horizons)
# ---------------------------------------------------------------------------

def plot_map_A(save: bool = True):
    """
    Carte A : choroplèthe AAL relatif (index baseline=1.0) par province.
    4 panneaux : Baseline / 2030 / 2050 / 2100 — scénario RCP 4.5.

    SOURCE projections : Dottori et al. (2018) Nat. Clim. Change 8:781-786
    SOURCE géo : Natural Earth 10m admin-1, CC0
    NOTE : modulation provinciale via fréquence EM-DAT (proxy, pas d'exposition fine)
    """
    from data.rcp_scenarios import EXPOSURE_GROWTH_RATE_ANNUAL

    geo = _load_geodata()
    scenario = "RCP45"
    horizons = [
        (2020, "Baseline\n2000–2020"),
        (2030, "2030"),
        (2050, "2050"),
        (2100, "2100"),
    ]

    cmap = mcm.get_cmap("YlOrRd")
    vmin, vmax = 0.9, 3.8

    fig, axes = plt.subplots(1, 4, figsize=(20, 6))
    fig.suptitle(
        "Carte A — Évolution temporelle du risque d'inondation (RCP 4.5)\n"
        "Indice d'AAL relatif par province (baseline 2020 = 1.0)",
        fontsize=13, fontweight="bold", y=1.02,
    )

    norm = Normalize(vmin=vmin, vmax=vmax)

    for ax, (yr, label) in zip(axes, horizons):
        _setup_map_ax(ax, label, fontsize=12)
        _draw_context(ax, geo)

        # Calcul du facteur d'AAL pour cette année
        if yr <= 2020:
            aal_index = {p: 1.0 for p in PROVINCES}
        else:
            dT_c, _, _ = get_warming_at_year(scenario, yr)
            delta_c, _, _ = get_damage_factor(dT_c)
            t_el = yr - 2020
            exp_f = (1 + EXPOSURE_GROWTH_RATE_ANNUAL) ** t_el
            base_factor = (1 + delta_c) * exp_f

            # Modulation par province : provinces Meuse > Escaut
            hazard_d = get_hazard_index_by_province(scenario, yr)
            max_freq  = max(v["freq_annual"] for v in hazard_d.values())
            aal_index = {}
            for pname, hdata in hazard_d.items():
                mod = 0.85 + 0.30 * (hdata["freq_annual"] / max_freq)
                aal_index[pname] = base_factor * mod

        # Ajouter Limbourg (valeur basse — peu exposé)
        aal_index_with_limburg = dict(aal_index)
        if yr > 2020:
            aal_index_with_limburg["Limburg_placeholder"] = base_factor * 0.75

        # Construire GDF
        gdf = geo["be_prov"].copy()
        vals = []
        for _, row in gdf.iterrows():
            ne_name    = row["name"]
            model_name = NE_TO_MODEL.get(ne_name)
            if model_name and model_name in aal_index:
                vals.append(aal_index[model_name])
            else:
                # Limbourg — valeur basse
                dT_c2, _, _ = get_warming_at_year(scenario, yr) if yr > 2020 else (0, 0, 0)
                delta_c2, _, _ = get_damage_factor(dT_c2) if yr > 2020 else (0, 0, 0)
                t_el2 = max(0, yr - 2020)
                exp_f2 = (1 + EXPOSURE_GROWTH_RATE_ANNUAL) ** t_el2
                vals.append((1 + delta_c2) * exp_f2 * 0.75 if yr > 2020 else 1.0)
        gdf["aal_index"] = vals

        # Choroplèthe
        gdf.plot(
            column="aal_index",
            ax=ax,
            cmap=cmap,
            norm=norm,
            edgecolor="#555555",
            linewidth=0.7,
            zorder=3,
            legend=False,
            missing_kwds={"color": "#cccccc"},
        )
        # Frontières provinciales
        gdf.boundary.plot(ax=ax, color="#333333", linewidth=0.5, zorder=4)
        # Rivières
        _draw_rivers(ax, geo)
        # Labels
        _add_province_labels(ax, gdf, fontsize=5.5)

        # Valeur médiane affichée
        median_val = np.nanmedian(vals)
        ax.text(0.02, 0.97,
                f"× {median_val:.2f}\n(médiane)",
                transform=ax.transAxes,
                fontsize=7, va="top", ha="left",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                          alpha=0.85, edgecolor="#cccccc"),
                zorder=10)

    # Colorbar dans un axe dédié à droite
    fig.subplots_adjust(right=0.88, wspace=0.08)
    cbar_ax = fig.add_axes([0.90, 0.18, 0.018, 0.62])
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cbar_ax)
    cbar.set_label("Indice d'AAL relatif\n(baseline 2020 = 1.0)", fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    _add_source_fig(
        fig,
        "Sources géographiques : Natural Earth 10m admin-1 (CC0, naciscdn.org)  ·  "
        "Projections : Dottori et al. (2018) Nat. Clim. Change 8:781–786 [Δdommages vs °C]  ·  "
        "IPCC AR5 (2014) Table SPM.2 [réchauffement RCP 4.5]  ·  "
        "Winsemius et al. (2016) [exposition]  ·  EM-DAT/CRED [fréquence historique]  ·  "
        "NOTE : modulation provinciale = proxy basé sur fréquence EM-DAT (pas d'exposition fine)",
        y=-0.03,
    )

    if save:
        path = os.path.join(OUTPUT_DIR, "carte_A_temporelle_RCP45.png")
        fig.savefig(path, dpi=300, bbox_inches="tight")
        print(f"  ✓ Carte A : {path}")
    return fig


# ---------------------------------------------------------------------------
# CARTE B — Comparaison inter-scénarios à 2100
# ---------------------------------------------------------------------------

def plot_map_B(save: bool = True):
    """
    Carte B : Augmentation des dommages (%) vs baseline, 4 scénarios RCP à 2100.
    Choroplèthe divergente : blanc=0%, rouge foncé=+250%+.

    SOURCE : Dottori et al. (2018) + IPCC AR5 (2014)
    SOURCE géo : Natural Earth 10m admin-1, CC0
    NOTE : modulation provinciale via fréquence EM-DAT (proxy, pas d'exposition fine)
    """
    from data.rcp_scenarios import EXPOSURE_GROWTH_RATE_ANNUAL

    geo = _load_geodata()
    yr  = 2100
    scenario_keys = ["RCP26", "RCP45", "RCP60", "RCP85"]

    fig, axes = plt.subplots(1, 4, figsize=(22, 6))
    fig.suptitle(
        "Carte B — Augmentation des dommages d'inondation à 2100 par scénario RCP (%)\n"
        "Incl. effet changement climatique + croissance de l'exposition économique",
        fontsize=12, fontweight="bold", y=1.02,
    )

    cmap = mcm.get_cmap("RdYlBu_r")
    norm = TwoSlopeNorm(vmin=0, vcenter=80, vmax=260)

    t_el  = yr - 2020
    exp_f = (1 + EXPOSURE_GROWTH_RATE_ANNUAL) ** t_el

    for ax, scen_key in zip(axes, scenario_keys):
        scen_info = SCENARIOS[scen_key]
        dT_c, dT_lo, dT_hi = get_warming_at_year(scen_key, yr)
        delta_c, _, _ = get_damage_factor(dT_c)
        total_increase_pct = ((1 + delta_c) * exp_f - 1.0) * 100.0

        is_extrap = (dT_c > 3.0)

        # Modulation provinciale (provinces Meuse plus affectées)
        hazard_d  = get_hazard_index_by_province(scen_key, yr)
        max_freq   = max(v["freq_annual"] for v in hazard_d.values())

        prov_values = {}
        for pname, hdata in hazard_d.items():
            mod = 0.85 + 0.30 * (hdata["freq_annual"] / max_freq)
            prov_values[pname] = total_increase_pct * mod

        gdf = geo["be_prov"].copy()
        vals = []
        for _, row in gdf.iterrows():
            ne_name    = row["name"]
            model_name = NE_TO_MODEL.get(ne_name)
            if model_name and model_name in prov_values:
                vals.append(prov_values[model_name])
            else:
                vals.append(total_increase_pct * 0.75)
        gdf["increase_pct"] = vals

        _setup_map_ax(
            ax,
            f"{scen_info['label']}\n+{dT_c:.1f}°C [{dT_lo:.1f}–{dT_hi:.1f}°C]",
            fontsize=10,
        )
        _draw_context(ax, geo)

        gdf.plot(
            column="increase_pct",
            ax=ax,
            cmap=cmap,
            norm=norm,
            edgecolor="#444444",
            linewidth=0.7,
            zorder=3,
            legend=False,
        )
        gdf.boundary.plot(ax=ax, color="#333333", linewidth=0.5, zorder=4)
        _draw_rivers(ax, geo)
        _add_province_labels(ax, gdf, fontsize=5.5)

        # Annotation médiane
        med = np.nanmedian(vals)
        ax.text(0.02, 0.97,
                f"+{med:.0f}%\n(médiane)",
                transform=ax.transAxes,
                fontsize=7.5, va="top", ha="left",
                color="#b2182b" if med > 100 else "#333333",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                          alpha=0.85, edgecolor="#cccccc"),
                zorder=10)

        if is_extrap:
            ax.text(0.98, 0.03,
                    "⚠ extrapolation\n> domaine Dottori",
                    transform=ax.transAxes, fontsize=6,
                    color="darkred", ha="right", va="bottom",
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="lightyellow",
                              alpha=0.9, edgecolor="orange"))

    fig.subplots_adjust(right=0.88, wspace=0.08)
    cbar_ax = fig.add_axes([0.90, 0.18, 0.018, 0.62])
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cbar_ax)
    cbar.set_label("Augmentation dommages (%)\nvs baseline 2000–2020", fontsize=9)
    cbar.ax.tick_params(labelsize=8)
    # Ticks à 0, 50, 80(centre), 130, 200, 260
    cbar.set_ticks([0, 50, 80, 130, 200, 260])
    cbar.set_ticklabels(["0%", "50%", "80%\n(centre)", "130%", "200%", "260%"])

    _add_source_fig(
        fig,
        "Sources géo : Natural Earth 10m admin-1 (CC0)  ·  "
        "Projections : Dottori et al. (2018) Nat. Clim. Change 8:781–786  ·  "
        "IPCC AR5 (2014) Table SPM.2  ·  Winsemius et al. (2016) [exposition]  ·  "
        "NOTE : modulation provinciale = proxy basé sur fréquence EM-DAT  ·  "
        "⚠ RCP 8.5 (2100) : extrapolation au-delà du domaine de calibration Dottori (> 3°C)",
        y=-0.03,
    )

    if save:
        path = os.path.join(OUTPUT_DIR, "carte_B_scenarios_2100.png")
        fig.savefig(path, dpi=300, bbox_inches="tight")
        print(f"  ✓ Carte B : {path}")
    return fig


# ---------------------------------------------------------------------------
# CARTE C — Aléa actuel (fréquence historique)
# ---------------------------------------------------------------------------

def plot_map_C(save: bool = True):
    """
    Carte C : Fréquence historique des inondations (événements/décennie).
    Choroplèthe + tracé des bassins versants.

    SOURCE données : EM-DAT (CRED/UCLouvain) 1990-2023
    SOURCE géo : Natural Earth 10m, CC0
    """
    geo = _load_geodata()

    # Valeur pour Limbourg (non dans le modèle principal)
    freq_dict = {pname: d["freq_events_per_decade"]
                 for pname, d in PROVINCE_HAZARD.items()}

    gdf = geo["be_prov"].copy()
    vals = []
    for _, row in gdf.iterrows():
        ne_name    = row["name"]
        model_name = NE_TO_MODEL.get(ne_name)
        if model_name and model_name in freq_dict:
            vals.append(freq_dict[model_name])
        else:
            vals.append(LIMBURG_DATA["freq_events_per_decade"])
    gdf["freq"] = vals

    fig, ax = plt.subplots(figsize=(11, 9))
    fig.suptitle(
        "Carte C — Aléa actuel : Fréquence historique des inondations significatives\n"
        "par province belge (événements majeurs/décennie, 1990–2023)",
        fontsize=12, fontweight="bold",
    )

    cmap = mcm.get_cmap("Blues")
    norm = Normalize(vmin=0, vmax=4.0)

    _setup_map_ax(ax, "", fontsize=11)
    _draw_context(ax, geo)

    gdf.plot(
        column="freq", ax=ax, cmap=cmap, norm=norm,
        edgecolor="#444444", linewidth=0.8, zorder=3, legend=False,
    )
    gdf.boundary.plot(ax=ax, color="#333333", linewidth=0.6, zorder=4)

    river_patches = _draw_rivers(ax, geo)
    _add_province_labels(ax, gdf, fontsize=7)

    # Annotations bassins versants
    ax.text(5.3, 50.15, "Bassin\nde la MEUSE",
            fontsize=9.5, color="#0D47A1", fontweight="bold", ha="center",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                      alpha=0.85, edgecolor="#0D47A1", linewidth=1.2),
            zorder=11)
    ax.text(3.60, 51.15, "Bassin\nde l'ESCAUT",
            fontsize=9.5, color="#0D47A1", fontweight="bold", ha="center",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                      alpha=0.85, edgecolor="#1565C0", linewidth=1.2),
            zorder=11)

    # Colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, orientation="vertical",
                        fraction=0.03, pad=0.02, shrink=0.8)
    cbar.set_label("Fréquence (événements majeurs/décennie)\n1990–2023 — Source : EM-DAT/CRED",
                   fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    # Légende rivières
    ax.legend(handles=river_patches, loc="lower right",
              fontsize=8, title="Hydrographie", title_fontsize=8,
              framealpha=0.9)

    _add_source_fig(
        fig,
        "Sources données : EM-DAT/CRED (UCLouvain), https://www.emdat.be, 1990–2023  ·  "
        "Service Public de Wallonie (SPW) — bassins versants  ·  "
        "Sources géo : Natural Earth 10m admin-1 + rivers_lake_centerlines (CC0)  ·  "
        "ATTENTION : données EM-DAT incomplètes avant 1990",
        y=0.01,
    )

    plt.tight_layout()
    if save:
        path = os.path.join(OUTPUT_DIR, "carte_C_hazard_actuel.png")
        fig.savefig(path, dpi=300, bbox_inches="tight")
        print(f"  ✓ Carte C : {path}")
    return fig


# ---------------------------------------------------------------------------
# CARTE D — Exposition économique
# ---------------------------------------------------------------------------

def plot_map_D(save: bool = True):
    """
    Carte D : Valeur économique exposée (Mrd€) et % PIB en zone Q100 (proxy).
    Choroplèthe à double panneau.

    SOURCE PIB : Eurostat (2022) NUTS3
    SOURCE zones Q100 : VMM (Flandre); PGRI 2022 SPW (Wallonie)
    SOURCE géo : Natural Earth 10m admin-1, CC0
    """
    geo = _load_geodata()
    exposure = get_exposed_value_by_province(year=2020)

    exposed_beur = {p: v["exposed_value_BEUR"] for p, v in exposure.items()}
    flood_pct    = {p: PROVINCES[p]["flood_zone_pct_Q100"] for p in PROVINCES}

    fig, axes = plt.subplots(1, 2, figsize=(18, 8))
    fig.suptitle(
        "Carte D — Exposition économique en zone inondable (Q100, proxy) par province belge\n"
        "Valeur absolue (Mrd€) et part du PIB provincial exposée (%, 2020)",
        fontsize=12, fontweight="bold",
    )

    # --- Panneau gauche : valeur absolue Mrd€ ---
    ax = axes[0]
    ax.set_title("Valeur exposée (Mrd€)\n[PIB provincial × fraction Q100 (proxy)]",
                 fontsize=10, fontweight="bold")

    gdf_left = geo["be_prov"].copy()
    vals_left = []
    for _, row in gdf_left.iterrows():
        ne_name    = row["name"]
        model_name = NE_TO_MODEL.get(ne_name)
        if model_name and model_name in exposed_beur:
            vals_left.append(exposed_beur[model_name])
        else:
            vals_left.append(LIMBURG_DATA["gdp_BEUR"] * LIMBURG_DATA["flood_zone_pct_Q100"] / 100)
    gdf_left["exposed_beur"] = vals_left

    cmap1  = mcm.get_cmap("plasma")
    norm1  = Normalize(vmin=0, vmax=max(vals_left) * 1.05)

    _setup_map_ax(ax, "", fontsize=10)
    _draw_context(ax, geo)
    gdf_left.plot(
        column="exposed_beur", ax=ax, cmap=cmap1, norm=norm1,
        edgecolor="#444444", linewidth=0.8, zorder=3, legend=False,
    )
    gdf_left.boundary.plot(ax=ax, color="#333333", linewidth=0.5, zorder=4)
    _draw_rivers(ax, geo)
    _add_province_labels(ax, gdf_left, fontsize=6.5)

    sm1 = plt.cm.ScalarMappable(cmap=cmap1, norm=norm1)
    sm1.set_array([])
    cbar1 = fig.colorbar(sm1, ax=ax, orientation="vertical",
                         fraction=0.04, pad=0.02, shrink=0.8)
    cbar1.set_label("Valeur exposée (Mrd€)\n[PIB × fraction Q100 (proxy)]", fontsize=9)

    # --- Panneau droit : % du PIB en zone Q100 ---
    ax = axes[1]
    ax.set_title("Part du PIB provincial en zone Q100 (%)\n[Fraction en zone inondable centennale (proxy)]",
                 fontsize=10, fontweight="bold")

    gdf_right = geo["be_prov"].copy()
    vals_right = []
    for _, row in gdf_right.iterrows():
        ne_name    = row["name"]
        model_name = NE_TO_MODEL.get(ne_name)
        if model_name and model_name in flood_pct:
            vals_right.append(flood_pct[model_name])
        else:
            vals_right.append(LIMBURG_DATA["flood_zone_pct_Q100"])
    gdf_right["flood_pct"] = vals_right

    cmap2  = mcm.get_cmap("YlOrRd")
    norm2  = Normalize(vmin=0, vmax=max(vals_right) * 1.05)

    _setup_map_ax(ax, "", fontsize=10)
    _draw_context(ax, geo)
    gdf_right.plot(
        column="flood_pct", ax=ax, cmap=cmap2, norm=norm2,
        edgecolor="#444444", linewidth=0.8, zorder=3, legend=False,
    )
    gdf_right.boundary.plot(ax=ax, color="#333333", linewidth=0.5, zorder=4)
    _draw_rivers(ax, geo)
    _add_province_labels(ax, gdf_right, fontsize=6.5)

    sm2 = plt.cm.ScalarMappable(cmap=cmap2, norm=norm2)
    sm2.set_array([])
    cbar2 = fig.colorbar(sm2, ax=ax, orientation="vertical",
                         fraction=0.04, pad=0.02, shrink=0.8)
    cbar2.set_label("Zone inondable Q100 (% superficie, proxy)\nVMM (Fl.) / PGRI-SPW (Wal.)", fontsize=9)

    _add_source_fig(
        fig,
        "Sources PIB : Eurostat (2022) NUTS3 Regional GDP (estimation)  ·  "
        "Zones inondables Q100 : VMM (Flandre) ; Plan de Gestion du Risque d'Inondation 2022 (SPW, Wallonie)  ·  "
        "Géo : Natural Earth 10m (CC0)  ·  "
        "NOTE : PIB = proxy de la valeur des actifs exposés ; fractions Q100 simplifiées (pas des cartes officielles)",
        y=0.00,
    )

    plt.tight_layout()
    if save:
        path = os.path.join(OUTPUT_DIR, "carte_D_exposition.png")
        fig.savefig(path, dpi=300, bbox_inches="tight")
        print(f"  ✓ Carte D : {path}")
    return fig


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def generate_all_maps():
    """Génère les 4 séries de cartes (A, B, C, D) avec données Natural Earth."""
    print("\n--- Génération des cartes géographiques (choroplèthes geopandas) ---")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Pré-charger les données une seule fois
    _load_geodata()

    figs = {}
    for name, func in [("A", plot_map_A), ("B", plot_map_B),
                        ("C", plot_map_C), ("D", plot_map_D)]:
        try:
            figs[name] = func()
            plt.close("all")
        except Exception as e:
            import traceback
            print(f"  ✗ Carte {name} — erreur : {e}")
            traceback.print_exc()

    print(f"  → {len(figs)}/4 cartes générées.")
    return figs
