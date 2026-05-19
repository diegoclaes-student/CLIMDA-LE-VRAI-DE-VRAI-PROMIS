from typing import Optional
# =============================================================================
# models/hazard_model.py
# Modèle d'aléa (Hazard) — CLIMADA component 1/3
# Projections RCP basées sur Dottori et al. (2018) et Alfieri et al. (2015/2018)
# =============================================================================

import numpy as np
from data.rcp_scenarios import (
    SCENARIOS, PROJECTION_YEARS, TIME_HORIZONS,
    get_damage_factor, get_warming_at_year,
)
from data.historical_belgium import (
    EP_POWER_LAW_PARAMS, AAL_BASELINE, RIVER_BASINS, ANNUAL_FREQUENCY,
)


# ---------------------------------------------------------------------------
# 1. Courbe EP (Exceedance Probability) baseline
# ---------------------------------------------------------------------------

EP_MAX_RETURN_PERIOD_YEARS = 1000  # au-delà : pas de calibration de queue explicite


def compute_ep_curve_baseline(
    return_periods: Optional[np.ndarray] = None,
) -> dict:
    """
    Calcule la courbe OEP (Occurrence Exceedance Probability) baseline.

    Modèle : loi de puissance calibrée sur données EM-DAT + Kreienkamp et al. (2021).
    L(T) = scale × T^exponent  (en M€)

    SOURCE calibration: Kreienkamp et al. (2021) DOI 10.25561/88185
    SOURCE AAL: Swiss Re Sigma (2023) — 0.03-0.05% PIB/an

    Note: au-delà de 1 000 ans, la queue n'est pas calibrée (pas de GPD/GEV),
    donc les pertes sont plafonnées à la valeur T=1 000 pour éviter des
    extrapolations non justifiées.

    Returns:
        dict avec clés 'return_periods', 'losses_MEUR', 'losses_low', 'losses_high',
        'exceedance_prob', 'annual_rate'
    """
    if return_periods is None:
        return_periods = np.logspace(0, 3, 200)  # 1 an → 1 000 ans (cap)

    params = EP_POWER_LAW_PARAMS
    scale    = params["scale"]        # M€
    exponent = params["exponent"]     # 0.683

    # Pertes centrales : L(T) = scale × T^exponent, avec cap de queue
    rp = np.asarray(return_periods, dtype=float)
    rp_capped = np.minimum(rp, EP_MAX_RETURN_PERIOD_YEARS)
    losses_central = scale * rp_capped ** exponent

    # Incertitude : propagation depuis l'incertitude de calibration
    # Facteur ±30% sur le scale, ±0.05 sur l'exposant (estimé depuis EM-DAT uncertainty)
    losses_low  = (scale * 0.60) * rp_capped ** (exponent - 0.08)
    losses_high = (scale * 1.60) * rp_capped ** (exponent + 0.08)

    # Probabilité de dépassement annuel : P(L > l) = 1/T
    exceedance_prob = 1.0 / return_periods
    annual_rate     = exceedance_prob

    return {
        "return_periods":    return_periods,
        "losses_MEUR":       losses_central,
        "losses_low_MEUR":   losses_low,
        "losses_high_MEUR":  losses_high,
        "exceedance_prob":   exceedance_prob,
        "annual_rate":       annual_rate,
        "source": (
            "Loi de puissance calibrée sur Kreienkamp et al. (2021) "
            "[T=400, L~6000 M€] et Swiss Re Sigma [AAL ~0.03-0.05% PIB]. "
            "Paramètres: scale=100 M€, exponent=0.683. "
            f"Queue plafonnée à T={EP_MAX_RETURN_PERIOD_YEARS} ans (pas de calibration GPD/GEV)."
        ),
    }


def compute_ep_curve_future(
    scenario: str,
    year: int,
    return_periods: Optional[np.ndarray] = None,
) -> dict:
    """
    Courbe EP future pour un scénario RCP et une année donnée.

    Méthode : multiplication de la courbe baseline par le facteur de dommages
    Dottori et al. (2018) correspondant au réchauffement projeté.

    Formula : L_RCP(T, year) = L_baseline(T) × (1 + Δ_damage(ΔT_RCP(year)))

    SOURCE: Dottori et al. (2018) Nat. Clim. Change 8:781-786
    SOURCE: Alfieri et al. (2015) — cohérence avec augmentation Q100
    """
    baseline = compute_ep_curve_baseline(return_periods)
    T = baseline["return_periods"]

    # Réchauffement projeté pour ce scénario et cette année
    dT_c, dT_lo, dT_hi = get_warming_at_year(scenario, year)

    # Facteurs de dommages (Dottori 2018)
    delta_c,  delta_lo,  delta_hi  = get_damage_factor(dT_c)
    delta_c2, delta_lo2, delta_hi2 = get_damage_factor(dT_lo)
    delta_c3, delta_lo3, delta_hi3 = get_damage_factor(dT_hi)

    # Application des facteurs
    mult_central = 1.0 + delta_c
    mult_low     = 1.0 + min(delta_lo, delta_lo2)
    mult_high    = 1.0 + max(delta_hi, delta_hi3)

    # Vérification extrapolation
    is_extrapolated = (dT_c > 3.0) or (dT_hi > 3.0)

    return {
        "scenario":          scenario,
        "year":              year,
        "return_periods":    T,
        "losses_MEUR":       baseline["losses_MEUR"] * mult_central,
        "losses_low_MEUR":   baseline["losses_low_MEUR"] * mult_low,
        "losses_high_MEUR":  baseline["losses_high_MEUR"] * mult_high,
        "exceedance_prob":   baseline["exceedance_prob"],
        "warming_C":         (dT_c, dT_lo, dT_hi),
        "damage_factor":     (mult_central, mult_low, mult_high),
        "is_extrapolated":   is_extrapolated,
        "source": (
            f"Dottori et al. (2018) Nat. Clim. Change 8:781-786. "
            f"Réchauffement {scenario} à {year}: {dT_c:.1f}°C [{dT_lo:.1f}–{dT_hi:.1f}°C] "
            f"(IPCC AR5 Table SPM.2). "
            f"Facteur dommages: ×{mult_central:.2f} [{mult_low:.2f}–{mult_high:.2f}]."
            + (" [EXTRAPOLATION]" if is_extrapolated else "")
        ),
    }


# ---------------------------------------------------------------------------
# 2. Projections temporelles de l'AAL
# ---------------------------------------------------------------------------

def compute_aal_projections() -> dict:
    """
    Calcule l'AAL projeté (M€/an) pour chaque scénario et chaque année 2020-2100.

    Composantes :
      1. Changement climatique : facteur Dottori et al. (2018)
      2. Croissance de l'exposition : facteur exponentiel basé sur Winsemius et al. (2016)

    Returns:
        dict: {scenario: {'years': [...], 'aal_c': [...], 'aal_lo': [...], 'aal_hi': [...]}}
    """
    from data.rcp_scenarios import EXPOSURE_GROWTH_RATE_ANNUAL

    results = {}
    aal_base = AAL_BASELINE["central_MEUR"]
    aal_base_lo = AAL_BASELINE["low_MEUR"]
    aal_base_hi = AAL_BASELINE["high_MEUR"]

    years = np.array(PROJECTION_YEARS)

    for scen_key in SCENARIOS:
        aal_c  = []
        aal_lo = []
        aal_hi = []

        for yr in years:
            # Composante changement climatique
            dT_c, dT_lo_val, dT_hi_val = get_warming_at_year(scen_key, yr)
            delta_c,  _,        _       = get_damage_factor(dT_c)
            delta_lo, _,        _       = get_damage_factor(dT_lo_val)
            delta_hi, _,        _       = get_damage_factor(dT_hi_val)

            # Composante exposition (croissance économique)
            # SOURCE: Winsemius et al. (2016) — part exposure = ~60% du risque total
            # Taux de croissance de l'exposition 1.2%/an
            t_elapsed = max(0, yr - 2020)
            exposure_factor = (1 + EXPOSURE_GROWTH_RATE_ANNUAL) ** t_elapsed

            # AAL total = AAL_baseline × (1 + Δ_climate) × exposure_factor
            # Séparation des incertitudes : CC sur le facteur climatique,
            # exposition sur la valeur baseline
            aal_c.append(aal_base    * (1 + delta_c)  * exposure_factor)
            aal_lo.append(aal_base_lo * (1 + delta_lo) * exposure_factor)
            aal_hi.append(aal_base_hi * (1 + delta_hi) * exposure_factor)

        results[scen_key] = {
            "years":  years.tolist(),
            "aal_c":  aal_c,
            "aal_lo": aal_lo,
            "aal_hi": aal_hi,
            "source": (
                "Dottori et al. (2018) [facteur CC] × "
                "Winsemius et al. (2016) [croissance exposition 1.2%/an] × "
                "Swiss Re Sigma [AAL baseline 216 M€/an]"
            ),
        }

    return results


# ---------------------------------------------------------------------------
# 3. Données d'aléa par province (pour les cartes)
# ---------------------------------------------------------------------------

# Fréquence historique des inondations par province
# Indice de fréquence normalisé sur 1980-2023 — calibré sur EM-DAT + SPW
# SOURCE: EM-DAT (CRED/UCLouvain); Service Public de Wallonie (SPW)

PROVINCE_HAZARD = {
    # Province: (freq_index_baseline, exposition_relative, basin)
    # freq_index = nombre moyen d'événements majeurs/décennie (EM-DAT, 1990-2023)
    "Liège": {
        "freq_events_per_decade": 3.5,   # EM-DAT — province la plus touchée (Vesdre, Meuse)
        "basin": "Meuse",
        "source": "EM-DAT (CRED/UCLouvain) 1990-2023; SPW données bassins versants",
    },
    "Namur": {
        "freq_events_per_decade": 2.8,
        "basin": "Meuse/Sambre",
        "source": "EM-DAT (CRED/UCLouvain) 1990-2023",
    },
    "Luxembourg": {
        "freq_events_per_decade": 2.5,
        "basin": "Meuse (Lesse, Ourthe)",
        "source": "EM-DAT (CRED/UCLouvain) 1990-2023",
    },
    "Hainaut": {
        "freq_events_per_decade": 2.0,
        "basin": "Escaut/Sambre",
        "source": "EM-DAT (CRED/UCLouvain) 1990-2023",
    },
    "West-Vlaanderen": {
        "freq_events_per_decade": 1.5,
        "basin": "Escaut/côtier",
        "source": "EM-DAT (CRED/UCLouvain) 1990-2023",
    },
    "Brabant Wallon": {
        "freq_events_per_decade": 1.5,
        "basin": "Meuse (Dyle)",
        "source": "EM-DAT (CRED/UCLouvain) 1990-2023",
    },
    "Oost-Vlaanderen": {
        "freq_events_per_decade": 1.2,
        "basin": "Escaut",
        "source": "EM-DAT (CRED/UCLouvain) 1990-2023",
    },
    "Bruxelles": {
        "freq_events_per_decade": 1.0,
        "basin": "Escaut (Senne)",
        "source": "EM-DAT (CRED/UCLouvain) 1990-2023",
    },
    "Antwerpen": {
        "freq_events_per_decade": 1.0,
        "basin": "Escaut",
        "source": "EM-DAT (CRED/UCLouvain) 1990-2023",
    },
    "Vlaams-Brabant": {
        "freq_events_per_decade": 0.8,
        "basin": "Escaut (Dyle)",
        "source": "EM-DAT (CRED/UCLouvain) 1990-2023",
    },
}


def get_hazard_index_by_province(
    scenario: Optional[str] = None,
    year: int = 2020,
) -> dict:
    """
    Retourne l'indice d'aléa par province (normalisé, baseline=1.0 pour 2020).
    Si scenario est fourni, applique le facteur de réchauffement Dottori.

    SOURCE: EM-DAT pour les valeurs baseline; Dottori et al. (2018) pour la projection.
    """
    result = {}
    for prov, data in PROVINCE_HAZARD.items():
        base_freq = data["freq_events_per_decade"] / 10.0  # → événements/an

        if scenario is not None and year > 2020:
            dT_c, dT_lo, dT_hi = get_warming_at_year(scenario, year)
            delta_c, delta_lo, delta_hi = get_damage_factor(dT_c)
            # Augmentation de la fréquence proportionnelle au facteur de dommages
            # (hypothèse conservative — en réalité la fréquence peut augmenter
            # davantage que la sévérité selon Alfieri 2015)
            freq_factor = 1.0 + delta_c * 0.5   # hypothèse : 50% de l'effet total sur la fréquence
            freq_future = base_freq * freq_factor
        else:
            freq_future = base_freq

        result[prov] = {
            "freq_annual": freq_future,
            "freq_baseline": base_freq,
            "ratio_vs_baseline": freq_future / base_freq,
            "source": data["source"],
        }
    return result
