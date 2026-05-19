# =============================================================================
# outputs/charts.py
# 6 graphiques analytiques pour le rapport
# =============================================================================

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import os
import warnings

from data.historical_belgium import (
    ANNUAL_FREQUENCY, FLOOD_EVENTS, AAL_BASELINE,
    DATA_QUALITY_NOTE, EP_POWER_LAW_PARAMS,
)
from data.rcp_scenarios import SCENARIOS, PROJECTION_YEARS, TIME_HORIZONS, DISCOUNT_RATES
from models.hazard_model import (
    compute_ep_curve_baseline, compute_ep_curve_future, compute_aal_projections,
)
from models.exposure_model import decompose_risk_increase
from models.risk_metrics import (
    compute_all_npv, compute_protection_gap_projections, ADAPTATION_MEASURES,
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs_generated", "figures")

# Palette colorblind-safe (ColorBrewer)
CB_COLORS = {
    "RCP26": "#2166ac",   # bleu
    "RCP45": "#4dac26",   # vert
    "RCP60": "#d01c8b",   # magenta
    "RCP85": "#b2182b",   # rouge
    "baseline": "#444444",
}

SCENARIO_LABELS = {
    "RCP26": "RCP 2.6 (faible forçage)",
    "RCP45": "RCP 4.5 (intermédiaire)",
    "RCP60": "RCP 6.0 (stabilisation tardive)",
    "RCP85": "RCP 8.5 (sans atténuation)",
}


def _add_source(ax, text, fontsize=6.5, y_offset=-0.13):
    ax.annotate(
        text, xy=(0.0, y_offset), xycoords="axes fraction",
        fontsize=fontsize, style="italic", color="#555555",
        wrap=True,
    )


# ---------------------------------------------------------------------------
# Graphique 1 — Série historique belge
# ---------------------------------------------------------------------------

def plot_chart1(save: bool = True):
    """
    Série historique des inondations belges (1980–2023).
    Avec test de tendance Mann-Kendall et annotation des événements majeurs.

    SOURCE données: EM-DAT (CRED/UCLouvain)
    SOURCE test: Mann-Kendall via scipy.stats ou pymannkendall
    """
    try:
        from scipy import stats as sstats
    except ImportError:
        sstats = None

    years = sorted(ANNUAL_FREQUENCY.keys())
    losses = [ANNUAL_FREQUENCY[y][1] if ANNUAL_FREQUENCY[y][1] is not None else 0.0
              for y in years]
    n_events = [ANNUAL_FREQUENCY[y][0] for y in years]

    # Test Mann-Kendall sur pertes (1990-2023) — exclure pré-1990
    analysis_years = [y for y in years if y >= 1990]
    analysis_losses = [ANNUAL_FREQUENCY[y][1] if ANNUAL_FREQUENCY[y][1] is not None else 0.0
                       for y in analysis_years]

    mk_result = None
    if sstats is not None:
        # Mann-Kendall test = test de rang de Kendall sur la série temporelle
        tau, p_value = sstats.kendalltau(analysis_years, analysis_losses)
        mk_result = {"tau": tau, "p_value": p_value}

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 9), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1]})
    fig.suptitle(
        "Graphique 1 — Série historique des inondations en Belgique (1980–2023)\n"
        "Fréquence et sévérité des événements majeurs",
        fontsize=13, fontweight="bold",
    )

    # --- Panneau supérieur : pertes ---
    bars = ax1.bar(
        years, losses, color="#4393c3", alpha=0.75, edgecolor="white",
        linewidth=0.5, label="Pertes totales (M€)",
        zorder=3,
    )

    # Coloration spéciale pour 2021
    ax1.bar([2021], [losses[years.index(2021)]], color="#b2182b", alpha=0.9,
            edgecolor="white", linewidth=0.5, zorder=4)

    ax1.set_ylabel("Pertes totales estimées (M€)", fontsize=10)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax1.grid(axis="y", alpha=0.4, zorder=0)
    ax1.axvline(1990, color="gray", linestyle="--", alpha=0.5, linewidth=1)
    ax1.text(1990.5, max(losses) * 0.88,
             "◄ Données EM-DAT\nincomplètes < 1990",
             fontsize=7.5, color="gray", va="top")

    # Annotations événements majeurs
    major_events = [e for e in FLOOD_EVENTS if e["losses_total_MEUR"] >= 250]
    for evt in major_events:
        yr = evt["year"]
        if yr in years:
            l = evt["losses_total_MEUR"]
            name = evt["event_name"].replace(" ", "\n")
            ax1.annotate(
                f"{name}\n{l:,.0f} M€",
                xy=(yr, l),
                xytext=(yr + (1 if yr < 2015 else -5), l * 0.85),
                fontsize=6.5, ha="left",
                arrowprops=dict(arrowstyle="->", color="#333333", lw=0.8),
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                          alpha=0.85, edgecolor="#cccccc"),
            )

    # AAL baseline en pointillés
    aal_c = AAL_BASELINE["central_MEUR"]
    aal_lo = AAL_BASELINE["low_MEUR"]
    aal_hi = AAL_BASELINE["high_MEUR"]
    ax1.axhline(aal_c, color="#f4a261", linestyle="--", linewidth=1.5,
                label=f"AAL baseline ~{aal_c:.0f} M€/an (Swiss Re Sigma)")
    ax1.fill_between(years, aal_lo, aal_hi, alpha=0.15, color="#f4a261",
                     label=f"IC AAL [{aal_lo:.0f}–{aal_hi:.0f} M€/an]")
    ax1.legend(fontsize=8, loc="upper left")

    # Mann-Kendall result
    if mk_result:
        sign = "↑ tendance à la hausse" if mk_result["tau"] > 0 else "↓ tendance à la baisse"
        pstr = f"p = {mk_result['p_value']:.3f}"
        sig = "(*significatif p<0.10)" if mk_result["p_value"] < 0.10 else "(non significatif)"
        ax1.text(0.98, 0.97,
                 f"Mann-Kendall (1990–2023)\nτ = {mk_result['tau']:.3f}, {pstr} {sig}\n"
                 "⚠ biais EM-DAT pré-2000 possible",
                 transform=ax1.transAxes, ha="right", va="top",
                 fontsize=8, color="#333333",
                 bbox=dict(boxstyle="round,pad=0.4", facecolor="lightyellow",
                           alpha=0.9, edgecolor="#cccccc"))

    # --- Panneau inférieur : fréquence ---
    ax2.bar(years, n_events, color="#74add1", alpha=0.7, edgecolor="white", zorder=3)
    ax2.bar([2021], [n_events[years.index(2021)]], color="#b2182b", alpha=0.9,
            edgecolor="white", zorder=4)
    ax2.set_ylabel("Nb événements", fontsize=9)
    ax2.set_xlabel("Année", fontsize=10)
    ax2.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax2.grid(axis="y", alpha=0.4, zorder=0)
    ax2.set_ylim(0, 3)
    ax2.axvline(1990, color="gray", linestyle="--", alpha=0.5, linewidth=1)

    _add_source(
        ax2,
        "Sources : EM-DAT/CRED (UCLouvain) — https://www.emdat.be · "
        "Assuralia (2021) [juillet 2021 : 2 500 M€ assurés, confirmé] · "
        "Swiss Re Sigma (2023) [AAL baseline] · "
        "ATTENTION : données < 1990 incomplètes (biais d'enregistrement EM-DAT) → "
        "test Mann-Kendall appliqué sur 1990–2023 uniquement",
        y_offset=-0.30,
    )

    plt.tight_layout()
    if save:
        path = os.path.join(OUTPUT_DIR, "graphique_1_serie_historique.png")
        fig.savefig(path, dpi=300, bbox_inches="tight")
        print(f"  ✓ Graphique 1 sauvegardé : {path}")
    return fig


# ---------------------------------------------------------------------------
# Graphique 2 — Projections AAL par scénario RCP avec IC
# ---------------------------------------------------------------------------

def plot_chart2(save: bool = True):
    """
    AAL projeté 2020-2100, 4 scénarios RCP + intervalles de confiance.

    Inclut : l'incertitude sur le réchauffement (IPCC AR5) ET
             l'incertitude sur les dommages (Dottori et al. 2018 range).

    SOURCE: Dottori et al. (2018) Nat. Clim. Change 8:781-786
    SOURCE: IPCC AR5 (2014) Table SPM.2
    SOURCE: Swiss Re Sigma (2023) [AAL baseline]
    SOURCE: Winsemius et al. (2016) [exposition]
    """
    projections = compute_aal_projections()

    fig, ax = plt.subplots(figsize=(13, 8))
    fig.suptitle(
        "Graphique 2 — AAL projeté d'inondation en Belgique (2020–2100)\n"
        "4 scénarios RCP avec intervalles de confiance 90%",
        fontsize=13, fontweight="bold",
    )

    for scen_key in ["RCP26", "RCP45", "RCP60", "RCP85"]:
        proj = projections[scen_key]
        y = proj["years"]
        c  = proj["aal_c"]
        lo = proj["aal_lo"]
        hi = proj["aal_hi"]
        color = CB_COLORS[scen_key]
        scen_info = SCENARIOS[scen_key]

        ax.plot(y, c, color=color, linewidth=2.2,
                linestyle=scen_info["linestyle"],
                label=SCENARIO_LABELS[scen_key])
        ax.fill_between(y, lo, hi, color=color, alpha=0.15)

    # Baseline historique
    ax.axhline(AAL_BASELINE["central_MEUR"], color="#444444", linestyle=":",
               linewidth=1.5, label=f"AAL baseline ~{AAL_BASELINE['central_MEUR']:.0f} M€/an")
    ax.fill_between(
        [min(PROJECTION_YEARS), max(PROJECTION_YEARS)],
        AAL_BASELINE["low_MEUR"], AAL_BASELINE["high_MEUR"],
        alpha=0.08, color="#444444",
    )

    # Événement 2021 pour calibration
    ax.annotate(
        "Juillet 2021\n2 500 M€ assurés\n(Assuralia 2021)",
        xy=(2021, AAL_BASELINE["central_MEUR"] * 1.05), fontsize=8,
        xytext=(2025, 450),
        arrowprops=dict(arrowstyle="->", color="#b2182b", lw=1),
        color="#b2182b",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                  alpha=0.9, edgecolor="#b2182b"),
    )

    ax.set_xlabel("Année", fontsize=11)
    ax.set_ylabel("AAL — Pertes Annuelles Moyennes (M€/an)", fontsize=11)
    ax.legend(fontsize=9, loc="upper left", framealpha=0.92)
    ax.grid(alpha=0.35)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.set_xlim(2018, 2103)
    ax.set_ylim(0, max(projections["RCP85"]["aal_hi"]) * 1.05)

    # Note sur l'incertitude
    ax.text(0.98, 0.04,
            "NOTE : Les intervalles de confiance sont larges\n"
            "car les modèles climatiques divergent significativement.\n"
            "C'est un résultat scientifique en soi (Alfieri et al. 2018).\n"
            "RCP 8.5 à 2100 : extrapolation au-delà du domaine Dottori.",
            transform=ax.transAxes, ha="right", va="bottom",
            fontsize=7.5, color="#444444",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="lightyellow",
                      alpha=0.9, edgecolor="#cccccc"))

    _add_source(
        ax,
        "Sources : Dottori et al. (2018) Nat. Clim. Change 8:781–786 [Δdommages vs °C] · "
        "IPCC AR5 (2014) Table SPM.2 [réchauffement par scénario] · "
        "Swiss Re Sigma (2023) [AAL baseline 0.03–0.05% PIB] · "
        "Winsemius et al. (2016) [croissance exposition 1.2%/an] · "
        "Alfieri et al. (2018) Climate 6(1):6 [incertitude inter-modèles]",
        y_offset=-0.08,
    )

    plt.tight_layout()
    if save:
        path = os.path.join(OUTPUT_DIR, "graphique_2_projections_RCP.png")
        fig.savefig(path, dpi=300, bbox_inches="tight")
        print(f"  ✓ Graphique 2 sauvegardé : {path}")
    return fig


# ---------------------------------------------------------------------------
# Graphique 3 — Décomposition CC vs Exposition
# ---------------------------------------------------------------------------

def plot_chart3(save: bool = True):
    """
    Décomposition de l'augmentation du risque : CC vs croissance exposition.
    Graphique en aires empilées (stacked area).

    SOURCE: Winsemius et al. (2016) Nat. Clim. Change 6:381-385 [méthodologie]
    SOURCE: Dottori et al. (2018) [facteur CC]
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes_flat = axes.ravel()
    fig.suptitle(
        "Graphique 3 — Décomposition de l'augmentation du risque d'inondation\n"
        "Part due au Changement Climatique vs Croissance de l'Exposition économique",
        fontsize=12, fontweight="bold",
    )

    scenarios_to_plot = ["RCP26", "RCP45", "RCP60", "RCP85"]

    for ax, scen_key in zip(axes_flat, scenarios_to_plot):
        years = np.array(PROJECTION_YEARS)
        aal_base = AAL_BASELINE["central_MEUR"]

        cc_parts   = []
        exp_parts  = []
        base_parts = []

        for yr in years:
            decomp = decompose_risk_increase(scen_key, yr, aal_base)
            base_parts.append(aal_base)
            cc_parts.append(max(decomp["delta_cc"], 0))
            exp_parts.append(max(decomp["delta_exposure"], 0))

        base_arr = np.array(base_parts)
        cc_arr   = np.array(cc_parts)
        exp_arr  = np.array(exp_parts)

        ax.fill_between(years, 0, base_arr,
                        color="#aaaaaa", alpha=0.6, label="AAL baseline (2020)")
        ax.fill_between(years, base_arr, base_arr + cc_arr,
                        color=CB_COLORS[scen_key], alpha=0.65,
                        label="Part CC (incl. interaction)")
        ax.fill_between(years, base_arr + cc_arr, base_arr + cc_arr + exp_arr,
                        color="#f4a261", alpha=0.65,
                        label="Part exposition (Winsemius 2016)")

        ax.plot(years, base_arr + cc_arr + exp_arr,
                color="k", linewidth=1.5, linestyle="-", zorder=5)

        ax.set_title(SCENARIO_LABELS[scen_key], fontsize=10, fontweight="bold",
                     color=CB_COLORS[scen_key])
        ax.set_xlabel("Année", fontsize=9)
        ax.set_ylabel("AAL (M€/an)", fontsize=9)
        ax.legend(fontsize=7.5, loc="upper left")
        ax.grid(alpha=0.3)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))

    _add_source(
        axes_flat[-1],
        "Sources : Winsemius et al. (2016) Nat. Clim. Change 6:381–385 [décomposition CC/exposition] · "
        "Dottori et al. (2018) [facteur CC] · "
        "Taux croissance exposition : 1.2%/an (Winsemius 2016; Eurostat/BNB historique) · "
        "interaction CC×exposition attribuée au CC",
        y_offset=-0.20,
    )

    plt.tight_layout()
    if save:
        path = os.path.join(OUTPUT_DIR, "graphique_3_decomposition_risque.png")
        fig.savefig(path, dpi=300, bbox_inches="tight")
        print(f"  ✓ Graphique 3 sauvegardé : {path}")
    return fig


# ---------------------------------------------------------------------------
# Graphique 4 — Courbes EP (Exceedance Probability)
# ---------------------------------------------------------------------------

def plot_chart4(save: bool = True):
    """
    OEP (Occurrence Exceedance Probability) :
    Baseline / RCP 4.5 à 2050 / RCP 8.5 à 2100

    Axe X log (période de retour 1 → 1000 ans)
    Lignes de référence T = 10, 50, 100, 200, 500 ans

    SOURCE: Kreienkamp et al. (2021) DOI 10.25561/88185 [calibration baseline]
    SOURCE: Alfieri et al. (2015) Global Env. Change 35:199-212 [facteurs Q100 futurs]
    SOURCE: Dottori et al. (2018) [facteurs dommages appliqués à la courbe baseline]
    """
    T_vals = np.logspace(0, 3, 300)  # 1 → 1000 ans (queue non calibrée au-delà)

    ep_base = compute_ep_curve_baseline(T_vals)
    ep_45_2050 = compute_ep_curve_future("RCP45", 2050, T_vals)
    ep_85_2100 = compute_ep_curve_future("RCP85", 2100, T_vals)

    fig, ax = plt.subplots(figsize=(12, 8))
    fig.suptitle(
        "Graphique 4 — Courbes de Probabilité de Dépassement (OEP)\n"
        "Pertes totales d'inondation en Belgique — baseline vs scénarios futurs",
        fontsize=13, fontweight="bold",
    )

    # Baseline
    ax.plot(T_vals, ep_base["losses_MEUR"] / 1000,
            color=CB_COLORS["baseline"], linewidth=2.5,
            label="Baseline (2000–2020)", zorder=5)
    ax.fill_between(T_vals,
                    ep_base["losses_low_MEUR"] / 1000,
                    ep_base["losses_high_MEUR"] / 1000,
                    color=CB_COLORS["baseline"], alpha=0.15)

    # RCP 4.5 à 2050
    ax.plot(T_vals, ep_45_2050["losses_MEUR"] / 1000,
            color=CB_COLORS["RCP45"], linewidth=2.2, linestyle="-",
            label=f"RCP 4.5 — 2050 (×{ep_45_2050['damage_factor'][0]:.2f})", zorder=5)
    ax.fill_between(T_vals,
                    ep_45_2050["losses_low_MEUR"] / 1000,
                    ep_45_2050["losses_high_MEUR"] / 1000,
                    color=CB_COLORS["RCP45"], alpha=0.15)

    # RCP 8.5 à 2100
    ax.plot(T_vals, ep_85_2100["losses_MEUR"] / 1000,
            color=CB_COLORS["RCP85"], linewidth=2.2, linestyle="-.",
            label=f"RCP 8.5 — 2100 (×{ep_85_2100['damage_factor'][0]:.2f}) ⚠ extrap.",
            zorder=5)
    ax.fill_between(T_vals,
                    ep_85_2100["losses_low_MEUR"] / 1000,
                    ep_85_2100["losses_high_MEUR"] / 1000,
                    color=CB_COLORS["RCP85"], alpha=0.12)

    # Lignes de référence
    ref_periods = [10, 50, 100, 200, 500]
    ref_colors  = ["#80cdc1", "#35978f", "#01665e", "#f5f5f5", "#bf812d"]
    for T_ref, col in zip(ref_periods, ref_colors):
        ax.axvline(T_ref, color=col, linestyle="--", linewidth=1.0, alpha=0.7)
        ax.text(T_ref * 1.05, 0.05,
                f"T={T_ref}",
                fontsize=7.5, color="#444444",
                rotation=90, va="bottom")

    # Point de calibration 2021
    ax.scatter([400], [6.0], color="#b2182b", s=120, zorder=10,
               marker="*", label="Juillet 2021 (~T=400, ~6 Mrd€) [Kreienkamp 2021]")
    ax.annotate("Juillet 2021\n~T=400 ans\n~6 Mrd€ total",
                xy=(400, 6.0), xytext=(200, 8.5),
                fontsize=8, color="#b2182b",
                arrowprops=dict(arrowstyle="->", color="#b2182b", lw=1),
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                          alpha=0.9, edgecolor="#b2182b"))

    ax.set_xscale("log")
    ax.set_xlabel("Période de retour (années)", fontsize=11)
    ax.set_ylabel("Perte totale (Mrd€)", fontsize=11)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}"))
    ax.legend(fontsize=9, loc="upper left", framealpha=0.92)
    ax.grid(True, which="both", alpha=0.3)
    ax.set_xlim(1, 3000)
    ax.set_ylim(0, max(ep_85_2100["losses_high_MEUR"]) / 1000 * 1.05)

    _add_source(
        ax,
        "Sources : Kreienkamp et al. (2021) WWA DOI 10.25561/88185 [calibration T=400, ~6 Mrd€] · "
        "Alfieri et al. (2015) Global Env. Change 35:199–212 [facteurs Q100 futurs, méthode] · "
        "Dottori et al. (2018) [multiplicateurs appliqués à la courbe baseline] · "
        "Swiss Re Sigma (2023) [AAL baseline 216 M€/an] · "
        "⚠ Queue non calibrée au-delà de T=1 000 ans (courbe plafonnée) · "
        "⚠ RCP 8.5 (2100) : extrapolation au-delà du domaine Dottori (> 3°C)",
        y_offset=-0.08,
    )

    plt.tight_layout()
    if save:
        path = os.path.join(OUTPUT_DIR, "graphique_4_EP_curves.png")
        fig.savefig(path, dpi=300, bbox_inches="tight")
        print(f"  ✓ Graphique 4 sauvegardé : {path}")
    return fig


# ---------------------------------------------------------------------------
# Graphique 5 — Protection gap
# ---------------------------------------------------------------------------

def plot_chart5(save: bool = True):
    """
    Pertes totales vs assurées par scénario × horizons.
    Protection gap (%) sur axe secondaire.
    SCR nat-cat Solvency II estimé.

    SOURCE: Swiss Re Sigma (2023); Assuralia (2022); EIOPA (2014)
    """
    from models.risk_metrics import compute_risk_table
    from models.vulnerability_model import INSURANCE_PARAMS

    rows = [r for r in compute_risk_table()
            if r["year"] in [2020, 2050, 2100]]

    # Préparer les données
    scenarios_plot = ["Baseline"] + [SCENARIOS[s]["label"] for s in SCENARIOS]
    years_plot = [2020, 2050, 2100]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
    fig.suptitle(
        "Graphique 5 — Protection Gap & SCR Nat-Cat Solvency II\n"
        "Pertes totales vs assurées par scénario (AAL en M€/an)",
        fontsize=12, fontweight="bold",
    )

    # --- Ax1 : barres groupées par scénario à 2100 ---
    scen_keys_ordered = ["Baseline", "RCP26", "RCP45", "RCP60", "RCP85"]
    scen_labels_ordered = {
        "Baseline": "Baseline\n2020",
        "RCP26": "RCP 2.6\n2100",
        "RCP45": "RCP 4.5\n2100",
        "RCP60": "RCP 6.0\n2100",
        "RCP85": "RCP 8.5\n2100",
    }
    coverage_pct = INSURANCE_PARAMS["natcat_coverage_pct_central"]

    aal_totals = []
    aal_insured = []
    aal_scr = []
    labels = []

    for r in compute_risk_table():
        if r["year"] == 2100 or r["scenario"] == "Baseline":
            if r["year"] in [2020, 2100]:
                labels.append(scen_labels_ordered.get(r["scenario"], r["scenario"]))
                t = r["aal_c_MEUR"]
                i = t * coverage_pct / 100
                aal_totals.append(t)
                aal_insured.append(i)
                aal_scr.append(r["scr_MEUR"])

    x = np.arange(len(labels))
    width = 0.35

    bars1 = ax1.bar(x - width/2, aal_totals, width, label="Pertes totales",
                    color="#4393c3", alpha=0.85, edgecolor="white")
    bars2 = ax1.bar(
        x + width/2,
        aal_insured,
        width,
        label=f"Pertes assurées (~{coverage_pct:.1f}%)",
        color="#f4a261",
        alpha=0.85,
        edgecolor="white",
    )

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=9)
    ax1.set_ylabel("AAL (M€/an)", fontsize=10)
    ax1.set_title("AAL : Pertes totales vs assurées", fontsize=11)
    ax1.legend(fontsize=9)
    ax1.grid(axis="y", alpha=0.35)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))

    # Axe secondaire : protection gap %
    ax1b = ax1.twinx()
    ax1b.axhline(100 - coverage_pct, color="#b2182b", linestyle="--",
                 linewidth=1.5, alpha=0.7)
    ax1b.set_ylabel(
        f"Protection gap (%) = {100 - coverage_pct:.1f}%\n"
        "(dérivé d'une part assurée 35–40%, Swiss Re Sigma 2023)",
        fontsize=8.5, color="#b2182b",
    )
    ax1b.set_ylim(0, 100)
    ax1b.tick_params(axis="y", colors="#b2182b")

    # --- Ax2 : SCR nat-cat Solvency II ---
    ax2.bar(x, aal_scr, color="#6a3d9a", alpha=0.8, edgecolor="white",
            label="SCR Nat-Cat approx. (VaR 99.5%)")
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, fontsize=9)
    ax2.set_ylabel("SCR Nat-Cat (M€)\n≈ PML-200 − AAL", fontsize=10)
    ax2.set_title("SCR Nat-Cat Solvency II (approximation)", fontsize=11)
    ax2.legend(fontsize=9)
    ax2.grid(axis="y", alpha=0.35)
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax2.text(0.02, 0.97,
             "ATTENTION : Approximation\nde la formule standard EIOPA.\n"
             "Voir EIOPA (2014) pour\nla formule exacte.",
             transform=ax2.transAxes, fontsize=7.5, va="top",
             bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow",
                       alpha=0.9, edgecolor="#cccccc"))

    _add_source(
        ax2,
        "Sources : Swiss Re Sigma (2023) [part assurée 35–40% → gap 60–65%] · "
        "Assuralia (2022) [pénétration assurance Belgique] · "
        "EIOPA (2014) Technical Specification [SCR Nat-Cat, formule approx.] · "
        "Dottori et al. (2018) [projections AAL]",
        y_offset=-0.12,
    )

    plt.tight_layout()
    if save:
        path = os.path.join(OUTPUT_DIR, "graphique_5_protection_gap.png")
        fig.savefig(path, dpi=300, bbox_inches="tight")
        print(f"  ✓ Graphique 5 sauvegardé : {path}")
    return fig


# ---------------------------------------------------------------------------
# Graphique 6 — Analyse coût-bénéfice adaptation
# ---------------------------------------------------------------------------

def plot_chart6(save: bool = True):
    """
    NPV des mesures d'adaptation vs inaction.
    Comparaison taux d'actualisation 3% vs 5% (recommandation CE 2014).

    SOURCE: Alfieri et al. (2016) Climatic Change 136:507-521
    SOURCE: European Commission (2014) Guide to CBA DOI 10.2776/97516
    """
    all_npv = compute_all_npv()

    # Filtrer pour RCP 4.5 2100 + 2 taux d'actualisation
    rcp45_3pct = [r for r in all_npv
                  if r["scenario"] == "RCP4.5-2100" and r["discount_label"] == "3%"]
    rcp45_5pct = [r for r in all_npv
                  if r["scenario"] == "RCP4.5-2100" and r["discount_label"] == "5%"]
    rcp85_3pct = [r for r in all_npv
                  if r["scenario"] == "RCP8.5-2100" and r["discount_label"] == "3%"]

    measure_names = [r["measure_name"] for r in rcp45_3pct]
    npv_45_3 = [r["npv_MEUR"] for r in rcp45_3pct]
    npv_45_5 = [r["npv_MEUR"] for r in rcp45_5pct]
    npv_85_3 = [r["npv_MEUR"] for r in rcp85_3pct]
    bc_45_3  = [r["bc_ratio"]  for r in rcp45_3pct]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
    fig.suptitle(
        "Graphique 6 — Analyse Coût-Bénéfice des Mesures d'Adaptation\n"
        "VAN (M€) sur durée de vie de la mesure — méthode ECA-CLIMADA",
        fontsize=12, fontweight="bold",
    )

    # --- Ax1 : NPV barres comparatives ---
    x = np.arange(len(measure_names))
    width = 0.25

    short_names = [n.replace(" ", "\n") for n in measure_names]

    ax1.bar(x - width, npv_45_3, width, label="RCP 4.5 — r=3%",
            color="#4393c3", alpha=0.85, edgecolor="white")
    ax1.bar(x,         npv_45_5, width, label="RCP 4.5 — r=5%",
            color="#92c5de", alpha=0.85, edgecolor="white")
    ax1.bar(x + width, npv_85_3, width, label="RCP 8.5 — r=3%",
            color="#b2182b", alpha=0.85, edgecolor="white")

    ax1.axhline(0, color="k", linewidth=1)
    ax1.set_xticks(x)
    ax1.set_xticklabels(short_names, fontsize=8)
    ax1.set_ylabel("VAN (M€)", fontsize=10)
    ax1.set_title("Valeur Actuelle Nette des mesures d'adaptation", fontsize=11)
    ax1.legend(fontsize=9)
    ax1.grid(axis="y", alpha=0.35)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))

    # Note sur l'assurance paramétrique (si incluse)
    if "Assurance paramétrique flood" in measure_names:
        idx_assur = measure_names.index("Assurance paramétrique flood")
        ax1.annotate(
            "NPV = 0 : ne réduit\npas le risque physique",
            xy=(idx_assur, 5),
            xytext=(idx_assur + 0.5, 200),
            fontsize=7.5,
            arrowprops=dict(arrowstyle="->", lw=0.8),
            bbox=dict(boxstyle="round,pad=0.2", facecolor="lightyellow", alpha=0.9),
        )

    # --- Ax2 : B/C ratio ---
    colors_bc = ["#4393c3" if bc >= 1 else "#d73027" for bc in bc_45_3]
    bars_bc = ax2.barh(short_names, bc_45_3, color=colors_bc, alpha=0.85,
                       edgecolor="white")
    ax2.axvline(1.0, color="k", linewidth=1.5, linestyle="--",
                label="B/C = 1 (seuil de rentabilité)")
    ax2.axvline(4.2, color="#4393c3", linewidth=1.0, linestyle=":",
                alpha=0.7, label="B/C digues Alfieri (2016)")
    ax2.axvline(12.0, color="#f4a261", linewidth=1.0, linestyle=":",
                alpha=0.7, label="B/C alerte précoce Alfieri (2016)")

    for bar, bc in zip(bars_bc, bc_45_3):
        ax2.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2,
                 f"{bc:.1f}×", va="center", fontsize=9, fontweight="bold")

    ax2.set_xlabel("Ratio Bénéfice / Coût", fontsize=10)
    ax2.set_title("B/C ratio — RCP 4.5, r = 3% (CE 2014)", fontsize=11)
    ax2.legend(fontsize=8, loc="lower right")
    ax2.grid(axis="x", alpha=0.35)
    ax2.set_xlim(0, max(bc_45_3) * 1.3)

    _add_source(
        ax2,
        "Sources : Alfieri et al. (2016) Climatic Change 136:507–521 [ordres de grandeur coûts/réductions] · "
        "European Commission (2014) Guide to CBA DOI 10.2776/97516 [taux d'actualisation 3% et 5%] · "
        "NOTE : mesures de transfert (assurance paramétrique) exclues du graphique · "
        "B/C issus du modèle (AAL × réduction) ; co-bénéfices écosystémiques et sociaux NON inclus",
        y_offset=-0.10,
    )

    plt.tight_layout()
    if save:
        path = os.path.join(OUTPUT_DIR, "graphique_6_cout_benefice.png")
        fig.savefig(path, dpi=300, bbox_inches="tight")
        print(f"  ✓ Graphique 6 sauvegardé : {path}")
    return fig


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def generate_all_charts():
    """Génère les 6 graphiques analytiques."""
    print("\n--- Génération des graphiques ---")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    figs = {}
    for i, func in enumerate([
        plot_chart1, plot_chart2, plot_chart3,
        plot_chart4, plot_chart5, plot_chart6,
    ], 1):
        try:
            figs[f"chart{i}"] = func()
        except Exception as e:
            print(f"  ✗ Graphique {i} — erreur : {e}")
            import traceback; traceback.print_exc()
    print(f"  → {len(figs)}/6 graphiques générés.")
    return figs
