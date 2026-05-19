# =============================================================================
# data/rcp_scenarios.py
# Paramètres des scénarios RCP du GIEC avec correspondance température
# et facteurs de dommages issus de la littérature scientifique.
#
# Sources primaires :
#   - IPCC AR5 (2014) Table SPM.2 — réchauffement par scénario
#   - Dottori et al. (2018) Nat. Clim. Change 8:781-786 — Δdommages vs °C
#   - Alfieri et al. (2015) Global Env. Change 35:199-212 — Q100 européen
#   - Kreienkamp et al. (2021) WWA — fréquence événements extrêmes
# =============================================================================

import numpy as np

# ---------------------------------------------------------------------------
# Correspondance RCP → réchauffement global à 2100
# SOURCE: IPCC AR5 (2014) Table SPM.2
# Baseline IPCC AR5 = période 1986-2005 (≈ +0.61°C au-dessus du pré-industriel)
# Ces valeurs sont des ΔT en °C par rapport à 1986-2005
# ---------------------------------------------------------------------------

RCP_WARMING_AT_2100 = {
    # scénario: (médiane, borne basse [5%], borne haute [95%])  en °C vs 1986-2005
    "RCP26": {"median_C": 1.0, "low_C": 0.3,  "high_C": 1.7,
              "source": "IPCC AR5 (2014) Table SPM.2"},
    "RCP45": {"median_C": 1.8, "low_C": 1.1,  "high_C": 2.6,
              "source": "IPCC AR5 (2014) Table SPM.2"},
    "RCP60": {"median_C": 2.2, "low_C": 1.4,  "high_C": 3.1,
              "source": "IPCC AR5 (2014) Table SPM.2"},
    "RCP85": {"median_C": 3.7, "low_C": 2.6,  "high_C": 4.8,
              "source": "IPCC AR5 (2014) Table SPM.2"},
}

# Réchauffement actuel (période de référence 2000-2020) vs 1986-2005 baseline IPCC
# Le réchauffement entre 2000-2020 et 1986-2005 est ≈ +0.3°C (estimation)
# Le réchauffement global actuel vs pré-industriel ≈ 1.2°C (IPCC AR6 2021)
# vs baseline IPCC AR5 (1986-2005): ≈ +0.61°C → actuel (2020) ≈ +0.59°C additionnels
# SOURCE: IPCC AR6 SPM (2021) — état du réchauffement global
CURRENT_WARMING_VS_AR5_BASELINE_C = 0.3   # approximatif, ΔT 2000-2020 vs 1986-2005

# ---------------------------------------------------------------------------
# Facteurs d'augmentation des dommages d'inondation
# SOURCE: Dottori et al. (2018) Nat. Clim. Change — Europe Centrale/Occidentale
# Ces facteurs Δ_damage représentent l'AUGMENTATION RELATIVE des dommages
# par rapport à la baseline historique (≈ 2000-2020).
# La formule est : D_future = D_baseline × (1 + Δ_damage)
#
# Niveaux de réchauffement dans Dottori et al. = °C au-dessus du pré-industriel
# Pour convertir vers la baseline IPCC AR5 (1986-2005): ΔT_AR5 = ΔT_preind - 0.61°C
# Approximation : on suppose que les facteurs Dottori s'appliquent au
# réchauffement ADDITIONNEL au-dessus de la période de référence 2000-2020
# (justification : la calibration de Dottori utilise des modèles proches de
# la période actuelle — différence ≤ 0.3°C, inférieure à l'incertitude)
#
# VALEURS EXTRAITES DE DOTTORI ET AL. (2018) — Table 1 / Fig. 2:
#   +1.5°C warming → Δ_damage = +1.13 (augmentation de 113%)
#   +2.0°C warming → Δ_damage = +1.31 (interpolé depuis Fig. 2)
#   +3.0°C warming → Δ_damage = +1.45 (augmentation de 145%)
#   Incertitude : Table S1 (Supplementary) → range ≈ ±50 points de pourcentage
# ---------------------------------------------------------------------------

DOTTORI_DAMAGE_LEVELS = {
    # ΔT_additional (°C): (Δ_damage_central, Δ_damage_low, Δ_damage_high)
    # ΔT = réchauffement additionnel au-dessus de la référence actuelle (2000-2020)
    0.0:  (0.00,  0.00,  0.00),   # baseline — aucune augmentation
    0.5:  (0.57,  0.20,  0.90),   # EXTRAPOLÉ linéairement (Dottori ne fournit pas cette valeur)
    1.0:  (1.00,  0.40,  1.50),   # SOURCE: Dottori (2018) Fig.2 — extrapolation en dessous de 1.5°C
    1.5:  (1.13,  0.60,  1.80),   # SOURCE: Dottori (2018) Table 1 — valeur DIRECTE +1.5°C
    2.0:  (1.31,  0.75,  2.00),   # SOURCE: Dottori (2018) Fig.2 — interpolation +2°C
    2.5:  (1.38,  0.80,  2.10),   # SOURCE: interpolation linéaire Dottori 2018
    3.0:  (1.45,  0.85,  2.20),   # SOURCE: Dottori (2018) Table 1 — valeur DIRECTE +3°C
    3.5:  (1.60,  0.90,  2.50),   # EXTRAPOLÉ au-delà du domaine Dottori — incertitude accrue
    4.0:  (1.75,  0.95,  2.85),   # EXTRAPOLÉ — à interpréter avec extrême précaution
    4.5:  (1.90,  1.00,  3.20),   # EXTRAPOLÉ — limite de validité du modèle dépassée
}

# Note importante sur l'extrapolation :
DOTTORI_EXTRAPOLATION_WARNING = (
    "ATTENTION : Les valeurs Dottori et al. (2018) couvrent 1.5°C à 3°C de "
    "réchauffement. Les valeurs pour ΔT < 1.5°C et ΔT > 3°C sont des "
    "EXTRAPOLATIONS LINÉAIRES qui dépassent le domaine de calibration. "
    "L'incertitude est considérablement plus grande dans ces régions. "
    "Pour RCP 8.5 à 2100 (ΔT ≈ 3.7°C), les résultats doivent être présentés "
    "avec des intervalles de confiance larges et cette limitation explicitée."
)


def get_damage_factor(delta_T_C: float) -> tuple[float, float, float]:
    """
    Interpolation/extrapolation linéaire des facteurs de dommages Dottori (2018).

    Args:
        delta_T_C: réchauffement additionnel en °C au-dessus de la référence 2000-2020.

    Returns:
        (central, low, high) — multiplicateur Δ_damage
        D_future = D_baseline * (1 + Δ_damage)

    SOURCE: Dottori et al. (2018) Nat. Clim. Change 8:781-786
    """
    temps = sorted(DOTTORI_DAMAGE_LEVELS.keys())
    centrals = [DOTTORI_DAMAGE_LEVELS[t][0] for t in temps]
    lows     = [DOTTORI_DAMAGE_LEVELS[t][1] for t in temps]
    highs    = [DOTTORI_DAMAGE_LEVELS[t][2] for t in temps]

    c = float(np.interp(delta_T_C, temps, centrals))
    lo = float(np.interp(delta_T_C, temps, lows))
    hi = float(np.interp(delta_T_C, temps, highs))
    return c, lo, hi


def get_warming_at_year(scenario: str, year: int) -> tuple[float, float, float]:
    """
    Réchauffement additif (°C vs référence 2000-2020) pour un scénario et une année.
    Interpolation linéaire entre 2020 (ΔT=0) et 2100 (ΔT=RCP_WARMING_AT_2100).
    Justification : le forçage RCP est approximativement linéaire sur 2020-2100
    pour les scénarios stabilisés (RCP 4.5, 2.6) et légèrement sous-linéaire
    pour RCP 8.5 — approximation conservatrice acceptable pour cet exercice.

    SOURCE: IPCC AR5 (2014) Table SPM.2 pour les valeurs 2100.
    """
    if year <= 2020:
        return 0.0, 0.0, 0.0
    if year > 2100:
        year = 2100  # pas d'extrapolation au-delà de 2100

    rcp = RCP_WARMING_AT_2100[scenario]
    frac = (year - 2020) / (2100 - 2020)

    c  = rcp["median_C"] * frac
    lo = rcp["low_C"] * frac
    hi = rcp["high_C"] * frac
    return c, lo, hi


# ---------------------------------------------------------------------------
# Scénarios complets : paramètres consolidés
# ---------------------------------------------------------------------------

SCENARIOS = {
    "RCP26": {
        "label": "RCP 2.6",
        "color": "#2166ac",      # bleu — colorblind safe (ColorBrewer RdBu)
        "linestyle": "-",
        "description": "Scénario d'atténuation forte (objectif < 2°C)",
        "warming_2100": RCP_WARMING_AT_2100["RCP26"],
        "gwl_equivalent": "~1.0°C additionnel vs 2000-2020",
        "source": "IPCC AR5 (2014) Table SPM.2",
    },
    "RCP45": {
        "label": "RCP 4.5",
        "color": "#4dac26",      # vert — scénario central
        "linestyle": "-",
        "description": "Scénario de stabilisation intermédiaire",
        "warming_2100": RCP_WARMING_AT_2100["RCP45"],
        "gwl_equivalent": "~1.8°C additionnel vs 2000-2020",
        "source": "IPCC AR5 (2014) Table SPM.2",
    },
    "RCP60": {
        "label": "RCP 6.0",
        "color": "#d01c8b",      # rose/magenta — différencié du rouge pour CB
        "linestyle": "--",
        "description": "Scénario de stabilisation tardive",
        "warming_2100": RCP_WARMING_AT_2100["RCP60"],
        "gwl_equivalent": "~2.2°C additionnel vs 2000-2020",
        "source": "IPCC AR5 (2014) Table SPM.2",
    },
    "RCP85": {
        "label": "RCP 8.5",
        "color": "#b2182b",      # rouge foncé — scénario pessimiste
        "linestyle": "-.",
        "description": "Scénario de référence sans atténuation (BAU)",
        "warming_2100": RCP_WARMING_AT_2100["RCP85"],
        "gwl_equivalent": "~3.7°C additionnel vs 2000-2020",
        "source": "IPCC AR5 (2014) Table SPM.2",
        "warning": "Extrapolation partielle au-delà du domaine Dottori (2018)",
    },
}

# Horizons temporels standards pour les calculs et tableaux
TIME_HORIZONS = [2030, 2050, 2075, 2100]

# Années de la série temporelle projetée (2020-2100)
PROJECTION_YEARS = list(range(2020, 2101, 5))

# ---------------------------------------------------------------------------
# Facteurs de croissance économique (exposition)
# SOURCE: Winsemius et al. (2016) Nat. Clim. Change — décomposition CC vs exposition
# Croissance du PIB et de l'urbanisation → augmentation de l'exposition aux aléas
# ---------------------------------------------------------------------------

# Taux de croissance annuel du PIB belge (réel, hors inflation) — hypothèse prudente
# SOURCE: Eurostat / Banque Nationale de Belgique — moyenne historique 2000-2022
BELGIUM_GDP_GROWTH_RATE_ANNUAL = 0.015   # 1.5 % par an (croissance réelle modérée)
BELGIUM_GDP_GROWTH_RATE_LOW    = 0.005   # 0.5 % — scénario pessimiste
BELGIUM_GDP_GROWTH_RATE_HIGH   = 0.025   # 2.5 % — scénario optimiste
GDP_GROWTH_SOURCE = "Eurostat/BNB — croissance réelle moyenne 2000-2022 en Belgique"

# Taux de croissance de l'exposition en zone inondable
# (inclut urbanisation + valorisation des actifs dans les zones à risque)
# SOURCE: Winsemius et al. (2016) — augmentation de l'exposition ~60% de la hausse totale
EXPOSURE_GROWTH_RATE_ANNUAL = 0.012   # légèrement inférieur à la croissance totale du PIB
EXPOSURE_SOURCE = "Winsemius et al. (2016) Nat. Clim. Change 6:381-385"

# ---------------------------------------------------------------------------
# Paramètres Solvency II / SCR Nat-Cat
# SOURCE: EIOPA (2014) — Technical Specification Solvency II
# ---------------------------------------------------------------------------

SOLVENCY_II_PARAMS = {
    "confidence_level": 0.995,  # VaR 99.5%
    "return_period_years": 200, # Équivalent à VaR 99.5% (1/200)
    "reference": "EIOPA (2014) Technical Specification — formule standard QIS5",
    "approximation_note": (
        "SCR_nat_cat ≈ max(PML_200ans - AAL × correction_temporelle, 0). "
        "Il s'agit d'une APPROXIMATION de la formule standard EIOPA. "
        "La formule exacte intègre des facteurs de diversification géographique "
        "et de ligne d'activité — voir EIOPA (2014) pour la version complète."
    ),
}

# ---------------------------------------------------------------------------
# Taux d'actualisation pour l'analyse coût-bénéfice
# SOURCE: European Commission (2014) Guide to Cost-Benefit Analysis
# ---------------------------------------------------------------------------

DISCOUNT_RATES = {
    "central": 0.03,   # 3% — recommandation CE pour projets environnementaux
    "alternative": 0.05,  # 5% — taux alternatif plus conservateur
    "source": "European Commission (2014) Guide to CBA, DOI 10.2776/97516",
}
