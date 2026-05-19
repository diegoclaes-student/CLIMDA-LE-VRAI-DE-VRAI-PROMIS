from typing import Optional
# =============================================================================
# models/risk_metrics.py
# Métriques actuarielles : AAL, EP curves, PML, SCR Solvency II, NPV adaptation
# =============================================================================

import numpy as np
from data.rcp_scenarios import SCENARIOS, TIME_HORIZONS, DISCOUNT_RATES, SOLVENCY_II_PARAMS
from data.historical_belgium import AAL_BASELINE, EP_POWER_LAW_PARAMS
from models.hazard_model import (
    compute_ep_curve_baseline,
    compute_ep_curve_future,
    compute_aal_projections,
)
from models.vulnerability_model import INSURANCE_PARAMS, split_insured_uninsured


# ---------------------------------------------------------------------------
# 1. AAL via intégration numérique de la courbe EP
# ---------------------------------------------------------------------------

def compute_aal_from_ep(ep_curve: dict) -> float:
    """
    AAL = ∫₀¹ L(p) dp ≈ Σᵢ Lᵢ × (pᵢ₋₁ - pᵢ₊₁) / 2   (trapèze)

    Équivalent à intégrer la courbe OEP sur la probabilité d'exceedance.

    SOURCE: Méthode numérique standard en actuariat catastrophe.
    Références: McNeil et al. (2015) "Quantitative Risk Management", Princeton UP.
    """
    p = ep_curve["exceedance_prob"]  # probabilités décroissantes
    L = ep_curve["losses_MEUR"]

    # Trier par probabilité croissante pour l'intégration
    idx = np.argsort(p)
    p_sorted = p[idx]
    L_sorted = L[idx]

    # Intégration trapèze : AAL = ∫ L(p) dp
    aal = np.trapz(L_sorted, p_sorted)
    return abs(aal)   # en M€/an


# ---------------------------------------------------------------------------
# 2. PML (Probable Maximum Loss) à différentes périodes de retour
# ---------------------------------------------------------------------------

def compute_pml(ep_curve: dict, return_period: float) -> float:
    """
    Retourne la perte probable maximale pour une période de retour donnée.

    PML(T) = L telle que P(L > L) = 1/T

    SOURCE: Définition standard actuariat catastrophe.
    """
    target_prob = 1.0 / return_period
    return float(np.interp(
        target_prob,
        ep_curve["exceedance_prob"][::-1],   # croissant
        ep_curve["losses_MEUR"][::-1],
    ))


# ---------------------------------------------------------------------------
# 3. Tableau complet de métriques par scénario × horizon
# ---------------------------------------------------------------------------

def compute_risk_table() -> list:
    """
    Génère le tableau 2 du rapport :
    Scénario | Horizon | °C | AAL [IC90%] | PML-100 | PML-200 | Protection gap | SCR

    SOURCE métriques:
      - AAL: Swiss Re Sigma + calibration EP (Kreienkamp 2021)
      - PML: intégration EP (Dottori 2018 projections)
      - SCR Solvency II: EIOPA (2014) Technical Specification
      - Protection gap: Swiss Re Sigma (2023); Assuralia (2022)
    """
    rows = []
    projections = compute_aal_projections()

    # Baseline 2020
    ep_base = compute_ep_curve_baseline()
    aal_base_c  = AAL_BASELINE["central_MEUR"]
    aal_base_lo = AAL_BASELINE["low_MEUR"]
    aal_base_hi = AAL_BASELINE["high_MEUR"]

    pml100_base = compute_pml(ep_base, 100)
    pml200_base = compute_pml(ep_base, 200)
    ins_base    = split_insured_uninsured(pml200_base)
    scr_base    = _compute_scr(pml200_base, aal_base_c)

    rows.append({
        "scenario":     "Baseline",
        "year":         2020,
        "warming_C_central": 0.0,
        "warming_C_low":     0.0,
        "warming_C_high":    0.0,
        "aal_c_MEUR":   aal_base_c,
        "aal_lo_MEUR":  aal_base_lo,
        "aal_hi_MEUR":  aal_base_hi,
        "pml100_MEUR":  pml100_base,
        "pml200_MEUR":  pml200_base,
        "protection_gap_pct": INSURANCE_PARAMS["protection_gap_pct_central"],
        "scr_MEUR":     scr_base,
        "source": (
            "Swiss Re Sigma (2023) [part assurée 35–40% → gap dérivé]; "
            "Kreienkamp et al. (2021); Assuralia (2022)"
        ),
    })

    for scen_key, scen_data in SCENARIOS.items():
        for yr in TIME_HORIZONS:
            from data.rcp_scenarios import get_warming_at_year, get_damage_factor

            dT_c, dT_lo, dT_hi = get_warming_at_year(scen_key, yr)
            delta_c, _, _ = get_damage_factor(dT_c)

            # AAL cohérent avec les projections (Graphique 2 / rapport)
            proj = projections[scen_key]
            idx = proj["years"].index(yr)
            aal_c  = proj["aal_c"][idx]
            aal_lo = proj["aal_lo"][idx]
            aal_hi = proj["aal_hi"][idx]

            # EP curve future
            ep_fut = compute_ep_curve_future(scen_key, yr)

            pml100 = compute_pml(ep_fut, 100)
            pml200 = compute_pml(ep_fut, 200)
            ins    = split_insured_uninsured(pml200)
            scr    = _compute_scr(pml200, aal_c)

            rows.append({
                "scenario":           scen_data["label"],
                "year":               yr,
                "warming_C_central":  dT_c,
                "warming_C_low":      dT_lo,
                "warming_C_high":     dT_hi,
                "aal_c_MEUR":         aal_c,
                "aal_lo_MEUR":        aal_lo,
                "aal_hi_MEUR":        aal_hi,
                "pml100_MEUR":        pml100,
                "pml200_MEUR":        pml200,
                "protection_gap_pct": ins["protection_gap_pct"],
                "scr_MEUR":           scr,
                "source": (
                    f"Dottori (2018) [ΔT={dT_c:.1f}°C → facteur ×{1+delta_c:.2f}]; "
                    "IPCC AR5 (2014) Table SPM.2; "
                    "EIOPA (2014) [SCR approx.]; Swiss Re Sigma (2023) "
                    "[part assurée 35–40% → gap dérivé]."
                ),
            })

    return rows


def _compute_scr(pml200_MEUR: float, aal_MEUR: float) -> float:
    """
    Approximation du SCR Nat-Cat selon la formule standard Solvency II.

    SCR_nat_cat ≈ max(PML_200ans - AAL × correction_temporelle, 0)

    ATTENTION : C'est une APPROXIMATION de la formule standard EIOPA.
    La formule exacte intègre des facteurs de corrélation entre lignes d'activité
    et zones géographiques. Voir EIOPA (2014) Technical Specification, Section 7.

    SOURCE: EIOPA (2014) — QIS5 Technical Specification, Natural Catastrophe module.
    Taux de confiance : VaR 99.5% sur 1 an = PML retour 200 ans.
    """
    # Correction temporelle (simplifié) : AAL représente la provision best estimate
    # SCR = capital requis au-delà du best estimate pour absorber un choc 1/200 ans
    scr = max(pml200_MEUR - aal_MEUR, 0.0)
    return scr


# ---------------------------------------------------------------------------
# 4. Analyse coût-bénéfice des mesures d'adaptation
# SOURCE: Alfieri et al. (2016) Climatic Change 136:507-521
# SOURCE méthodologie: European Commission (2014) Guide to CBA
# ---------------------------------------------------------------------------

ADAPTATION_MEASURES = [
    {
        "name": "Renforcement digues Meuse",
        "category": "adaptation",
        "cost_MEUR": 2_500.0,       # investissement total sur 10 ans, Wallonie
        "cost_source": "Alfieri et al. (2016) Climatic Change 136:507-521 [ordre de grandeur]",
        "risk_reduction_RCP45_pct": 35.0,   # % de réduction de l'AAL
        "risk_reduction_RCP85_pct": 25.0,   # moins efficace à réchauffement élevé
        "bc_ratio_source": "Modèle CLIMDA (AAL×réduction) calibré sur Alfieri et al. (2016)",
        "lifetime_years": 50,
        "note": "Efficacité réduite à RCP 8.5 : les digues sont dimensionnées pour T<200 ans",
    },
    {
        "name": "Systèmes d'alerte précoce",
        "category": "adaptation",
        "cost_MEUR": 150.0,
        "cost_source": "Alfieri et al. (2016) — early warning systems, ordre de grandeur EU",
        "risk_reduction_RCP45_pct": 20.0,   # réduction via évacuation préventive
        "risk_reduction_RCP85_pct": 18.0,
        "bc_ratio_source": "Modèle CLIMDA (AAL×réduction) — ordres de grandeur Alfieri 2016",
        "lifetime_years": 20,
        "note": "Rapport bénéfice/coût le plus élevé toutes mesures confondues",
    },
    {
        "name": "Reforestation bassins versants",
        "category": "adaptation",
        "cost_MEUR": 800.0,
        "cost_source": "Estimation JRC/Feyen — bassin Meuse, reforestation 100 000 ha",
        "risk_reduction_RCP45_pct": 15.0,
        "risk_reduction_RCP85_pct": 10.0,   # effet limité pour les événements extrêmes
        "bc_ratio_source": "Modèle CLIMDA (AAL×réduction) — Alfieri 2016 (pan-EU, ordre de grandeur)",
        "lifetime_years": 100,
        "note": "Ordre de grandeur pan-européen, incertitude élevée; co-bénéfices non comptabilisés",
    },
    {
        "name": "Zones d'expansion inondables",
        "category": "adaptation",
        "cost_MEUR": 1_200.0,       # coût foncier + réhabilitation
        "cost_source": "Alfieri et al. (2016) — floodplain restoration, ordre de grandeur",
        "risk_reduction_RCP45_pct": 25.0,
        "risk_reduction_RCP85_pct": 20.0,
        "bc_ratio_source": "Modèle CLIMDA (AAL×réduction) calibré sur Alfieri et al. (2016)",
        "lifetime_years": 75,
        "note": "Implique des relocalisations — coût social non inclus",
    },
    {
        "name": "Assurance paramétrique flood",
        "category": "transfer",
        "cost_MEUR": 200.0,         # prime annuelle sur 20 ans (actualisée)
        "cost_source": "Estimation basée sur Swiss Re Sigma (2023) — marché assurance paramétrique",
        "risk_reduction_RCP45_pct": 0.0,    # ne réduit pas l'aléa physique
        "risk_reduction_RCP85_pct": 0.0,    # mais réduit le protection gap financier
        "bc_ratio_source": "Outil de transfert de risque — B/C dépend du modèle actuariel",
        "lifetime_years": 20,
        "note": "N'est pas une mesure de RÉDUCTION du risque physique mais de transfert financier",
    },
]


def compute_npv_adaptation(
    measure: dict,
    aal_baseline_MEUR: float,
    aal_future_MEUR: float,
    discount_rate: float = 0.03,
    n_years: Optional[int] = None,
) -> dict:
    """
    NPV = Σₜ [(B(t) - C(t)) / (1+r)^t]

    B(t) = bénéfice annuel = réduction de l'AAL grâce à la mesure
    C(t) = coût annuel de la mesure (amorti sur sa durée de vie)

    SOURCE: Alfieri et al. (2016) Climatic Change 136:507-521 [méthodologie ECA-CLIMADA]
    SOURCE: European Commission (2014) Guide to CBA [taux d'actualisation 3%]
    """
    if n_years is None:
        n_years = measure["lifetime_years"]

    annual_cost = measure["cost_MEUR"] / n_years
    annual_benefit_central = aal_future_MEUR * measure["risk_reduction_RCP45_pct"] / 100.0

    # Flux annuels actualisés
    years = np.arange(1, n_years + 1)
    discount = (1 + discount_rate) ** (-years)

    npv = np.sum((annual_benefit_central - annual_cost) * discount)
    bc_ratio = np.sum(annual_benefit_central * discount) / np.sum(annual_cost * discount)

    return {
        "measure_name":       measure["name"],
        "npv_MEUR":           npv,
        "bc_ratio":           bc_ratio,
        "annual_benefit_MEUR": annual_benefit_central,
        "annual_cost_MEUR":   annual_cost,
        "discount_rate":      discount_rate,
        "n_years":            n_years,
        "source": (
            f"Alfieri et al. (2016) Climatic Change 136:507-521 [bénéfices]. "
            f"European Commission (2014) Guide CBA [r={discount_rate*100:.0f}%]. "
            f"Mesure: {measure['name']}."
        ),
    }


def compute_all_npv(aal_baseline_MEUR: float = 216.0, include_transfer: bool = False) -> list:
    """
    Calcule NPV pour toutes les mesures × {RCP 4.5, RCP 8.5} × {3%, 5%}.
    Par défaut, exclut les outils de transfert de risque (assurance paramétrique).
    """
    results = []

    # AAL futur 2100 pour RCP 4.5 et RCP 8.5
    from models.hazard_model import compute_aal_projections
    projs = compute_aal_projections()
    aal_rcp45_2100 = projs["RCP45"]["aal_c"][-1]   # dernier point (2100)
    aal_rcp85_2100 = projs["RCP85"]["aal_c"][-1]

    for measure in ADAPTATION_MEASURES:
        if not include_transfer and measure.get("category") == "transfer":
            continue
        for r_label, r in [("3%", 0.03), ("5%", 0.05)]:
            for scen_label, aal_fut, risk_pct in [
                ("RCP4.5-2100", aal_rcp45_2100, measure["risk_reduction_RCP45_pct"]),
                ("RCP8.5-2100", aal_rcp85_2100, measure["risk_reduction_RCP85_pct"]),
            ]:
                m = dict(measure)
                m["risk_reduction_RCP45_pct"] = risk_pct

                npv_result = compute_npv_adaptation(
                    m, aal_baseline_MEUR, aal_fut, discount_rate=float(r)
                )
                npv_result["scenario"] = scen_label
                npv_result["discount_label"] = r_label
                results.append(npv_result)

    return results


# ---------------------------------------------------------------------------
# 5. Protection gap projeté par scénario
# ---------------------------------------------------------------------------

def compute_protection_gap_projections() -> dict:
    """
    Pertes totales vs assurées pour chaque scénario × horizon 2100.
    Protection gap = pertes non assurées / pertes totales.

    SOURCE: Swiss Re Sigma (2023); Assuralia (2022)
    HYPOTHÈSE: le taux de couverture reste constant à 37.5%
    (dérivé d'une part assurée 35–40% Swiss Re Sigma 2023).
    Hypothèse conservative — en réalité, le marché pourrait évoluer.
    """
    from models.hazard_model import compute_aal_projections
    projs = compute_aal_projections()

    results = {}
    coverage = INSURANCE_PARAMS["natcat_coverage_pct_central"] / 100.0

    for scen_key, scen_data in SCENARIOS.items():
        aal_c  = projs[scen_key]["aal_c"]
        aal_lo = projs[scen_key]["aal_lo"]
        aal_hi = projs[scen_key]["aal_hi"]
        years  = projs[scen_key]["years"]

        results[scen_key] = {
            "years":          years,
            "aal_total_c":    aal_c,
            "aal_insured_c":  [x * coverage for x in aal_c],
            "aal_gap_c":      [x * (1 - coverage) for x in aal_c],
            "protection_gap_pct": (1 - coverage) * 100,
            "label":          scen_data["label"],
            "source": (
                "Swiss Re Sigma (2023) — part assurée nat-cat Europe: 35–40% "
                "(protection gap déduit 60–65%). "
                "Assuralia (2022) — couverture assurance habitation Belgique: 95%."
            ),
        }

    return results
