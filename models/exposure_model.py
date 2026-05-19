from typing import Optional
# =============================================================================
# models/exposure_model.py
# Modèle d'exposition économique — CLIMADA component 2/3
# Données belges provinciales basées sur Eurostat et statistiques nationales
# =============================================================================

import numpy as np
from data.rcp_scenarios import EXPOSURE_GROWTH_RATE_ANNUAL, EXPOSURE_SOURCE

# ---------------------------------------------------------------------------
# Données provinciales belges
# SOURCE PIB: Eurostat (2022) — NUTS 3 regional GDP (approx.)
# SOURCE superficie: Institut géographique national (IGN) Belgique
# SOURCE population: Statbel (2022)
# SOURCE zone inondable: Plan de Gestion du Risque d'Inondation (PGRI 2022),
#                        Vlaamse Milieumaatschappij (VMM)
# ---------------------------------------------------------------------------

PROVINCES = {
    "West-Vlaanderen": {
        # SOURCE PIB: Eurostat NUTS3 TL3 2022 estimate (BEL —approx.)
        "gdp_BEUR": 55.0,
        # SOURCE pop: Statbel (2022)
        "population_M": 1.20,
        # SOURCE superficie: IGN Belgique
        "area_km2": 3144,
        # Part de la superficie en zone inondable 1/100 ans (T=100)
        # SOURCE: VMM (Vlaamse Milieumaatschappij) — wateroverlast statistieken
        "flood_zone_pct_Q100": 8.5,
        # Coordonnée centroïde (lon, lat) — utilisée pour les cartes
        "centroid": (3.10, 50.96),
        # Bounding box approximatif (lon_min, lon_max, lat_min, lat_max)
        "bbox": (2.54, 3.37, 50.68, 51.37),
        "region": "Flandre",
    },
    "Oost-Vlaanderen": {
        "gdp_BEUR": 58.0,
        "population_M": 1.55,
        "area_km2": 2982,
        "flood_zone_pct_Q100": 10.0,  # Escaut, canaux
        "centroid": (3.72, 51.00),
        "bbox": (3.37, 4.25, 50.68, 51.37),
        "region": "Flandre",
    },
    "Antwerpen": {
        "gdp_BEUR": 90.0,   # port d'Anvers — PIB élevé
        "population_M": 1.88,
        "area_km2": 2867,
        "flood_zone_pct_Q100": 12.0,  # Escaut, Rupel
        "centroid": (4.58, 51.22),
        "bbox": (4.25, 5.15, 51.00, 51.50),
        "region": "Flandre",
    },
    "Vlaams-Brabant": {
        "gdp_BEUR": 52.0,
        "population_M": 1.17,
        "area_km2": 2106,
        "flood_zone_pct_Q100": 7.0,
        "centroid": (4.73, 50.88),
        "bbox": (4.25, 5.10, 50.64, 51.10),
        "region": "Flandre",
    },
    "Bruxelles": {
        "gdp_BEUR": 110.0,  # hub services financiers et européens
        "population_M": 1.22,
        "area_km2": 162,
        "flood_zone_pct_Q100": 5.0,   # Senne canalisée
        "centroid": (4.35, 50.85),
        "bbox": (4.29, 4.50, 50.79, 50.93),
        "region": "Bruxelles",
    },
    "Brabant Wallon": {
        "gdp_BEUR": 20.0,
        "population_M": 0.43,
        "area_km2": 1090,
        "flood_zone_pct_Q100": 11.0,  # Dyle, Orneau
        "centroid": (4.64, 50.58),
        "bbox": (4.43, 5.05, 50.38, 50.75),
        "region": "Wallonie",
    },
    "Hainaut": {
        "gdp_BEUR": 35.0,
        "population_M": 1.34,
        "area_km2": 3793,
        "flood_zone_pct_Q100": 9.0,   # Sambre, Haine
        "centroid": (4.00, 50.43),
        "bbox": (3.24, 4.45, 50.18, 50.75),
        "region": "Wallonie",
    },
    "Namur": {
        "gdp_BEUR": 15.0,
        "population_M": 0.50,
        "area_km2": 3666,
        "flood_zone_pct_Q100": 13.5,  # Meuse, Sambre, Lesse
        "centroid": (4.87, 50.27),
        "bbox": (4.43, 5.72, 49.85, 50.55),
        "region": "Wallonie",
    },
    "Liège": {
        "gdp_BEUR": 35.0,
        "population_M": 1.11,
        "area_km2": 3862,
        "flood_zone_pct_Q100": 15.0,  # Meuse, Vesdre, Ourthe — zone la plus exposée
        "centroid": (5.57, 50.45),
        "bbox": (5.00, 6.40, 50.25, 50.90),
        "region": "Wallonie",
    },
    "Luxembourg": {
        "gdp_BEUR": 10.0,
        "population_M": 0.29,
        "area_km2": 4440,
        "flood_zone_pct_Q100": 12.0,  # Semois, Lesse, Ourthe supérieure
        "centroid": (5.50, 49.83),
        "bbox": (4.98, 6.40, 49.45, 50.25),
        "region": "Wallonie",
    },
}

# Sources consolidées pour les données provinciales
PROVINCE_DATA_SOURCES = (
    "PIB provincial: Eurostat NUTS3 Regional GDP (2022) — données approx. "
    "Population: Statbel (2022). "
    "Superficie: IGN Belgique. "
    "Zone inondable Q100: VMM (Flandre); PGRI 2022 SPW (Wallonie) — "
    "fractions utilisées comme proxies simplifiés, pas des cartes Q100 officielles. "
    "NOTE: Les PIB provinciaux sont des ESTIMATIONS basées sur les clés régionales "
    "Eurostat et la structure économique belge — non directement publiés au NUTS3."
)


def get_province_names() -> list:
    """Liste des 10 provinces + Bruxelles."""
    return list(PROVINCES.keys())


def get_exposed_value_by_province(
    year: int = 2020,
    scenario: Optional[str] = None,
) -> dict:
    """
    Valeur économique exposée par province en Mrd€.
    = PIB × part en zone inondable × facteur de croissance.

    Hypothèse : le PIB est le proxy de la valeur des actifs exposés.
    (Hypothèse simplificatrice — en pratique, il faudrait utiliser
    les valeurs de stock de capital, pas le flux PIB)

    SOURCE: Eurostat (2022) pour le PIB; VMM/PGRI pour les zones inondables.
    """
    result = {}
    for prov, data in PROVINCES.items():
        # Croissance économique depuis 2020
        t_elapsed = max(0, year - 2020)
        growth_factor = (1 + EXPOSURE_GROWTH_RATE_ANNUAL) ** t_elapsed

        gdp_year = data["gdp_BEUR"] * growth_factor
        flood_frac = data["flood_zone_pct_Q100"] / 100.0

        # Valeur exposée = PIB × fraction en zone inondable
        exposed_value = gdp_year * flood_frac

        result[prov] = {
            "gdp_BEUR": gdp_year,
            "flood_zone_pct": data["flood_zone_pct_Q100"],
            "exposed_value_BEUR": exposed_value,
            "exposed_value_MEUR": exposed_value * 1000,
            "region": data["region"],
            "centroid": data["centroid"],
            "source": PROVINCE_DATA_SOURCES,
        }
    return result


def get_total_exposure_belgium(year: int = 2020) -> dict:
    """
    Exposition totale Belgique (M€) avec décomposition régionale.

    SOURCE: Eurostat (2022) PIB Belgique = 550 Brd€.
    """
    province_data = get_exposed_value_by_province(year)

    total_meur = sum(v["exposed_value_MEUR"] for v in province_data.values())
    by_region = {"Flandre": 0.0, "Wallonie": 0.0, "Bruxelles": 0.0}
    for prov, v in province_data.items():
        by_region[v["region"]] += v["exposed_value_MEUR"]

    return {
        "total_MEUR": total_meur,
        "by_region_MEUR": by_region,
        "year": year,
        "source": (
            "Eurostat (2022) PIB Belgique ~550 Brd€; "
            "VMM/PGRI zones inondables Q100; "
            "Winsemius et al. (2016) — taux de croissance exposition."
        ),
    }


# ---------------------------------------------------------------------------
# Décomposition CC vs Exposition (pour le graphique 3)
# SOURCE: Winsemius et al. (2016) Nat. Clim. Change 6:381-385
# ---------------------------------------------------------------------------

def decompose_risk_increase(
    scenario: str,
    year: int,
    aal_baseline_MEUR: float = 216.0,
) -> dict:
    """
    Décompose l'augmentation de l'AAL entre :
    (1) effet changement climatique (Dottori 2018)
    (2) effet croissance de l'exposition (Winsemius 2016)

    Note : l'interaction CC × exposition est attribuée au terme CC
    (car l'effet climatique s'applique sur une base d'actifs plus large).

    SOURCE: Winsemius et al. (2016) — méthodologie de décomposition
    SOURCE: Dottori et al. (2018) — facteur CC
    """
    from data.rcp_scenarios import get_warming_at_year, get_damage_factor

    dT_c, _, _ = get_warming_at_year(scenario, year)
    delta_c, _, _ = get_damage_factor(dT_c)

    t_elapsed = max(0, year - 2020)
    exposure_factor = (1 + EXPOSURE_GROWTH_RATE_ANNUAL) ** t_elapsed

    # AAL total (CC + exposition)
    aal_total = aal_baseline_MEUR * (1 + delta_c) * exposure_factor

    # Augmentations absolues (avec interaction attribuée au CC)
    delta_cc  = aal_baseline_MEUR * delta_c * exposure_factor
    delta_exp = aal_baseline_MEUR * (exposure_factor - 1)
    delta_tot = aal_total - aal_baseline_MEUR

    return {
        "scenario":       scenario,
        "year":           year,
        "aal_baseline":   aal_baseline_MEUR,
        "aal_total":      aal_total,
        "delta_cc":       delta_cc,         # M€ — part due au CC
        "delta_exposure": delta_exp,         # M€ — part due à l'exposition
        "delta_total":    delta_tot,
        "share_cc_pct":   100 * delta_cc  / delta_tot if delta_tot > 0 else 0,
        "share_exp_pct":  100 * delta_exp / delta_tot if delta_tot > 0 else 0,
        "source": (
            "Winsemius et al. (2016) Nat. Clim. Change 6:381-385 [méthodologie décomposition]. "
            "Dottori et al. (2018) [facteur CC]. "
            f"Réchauffement {scenario} à {year}: {dT_c:.1f}°C. "
            f"Facteur exposition: ×{exposure_factor:.2f}."
        ),
    }
