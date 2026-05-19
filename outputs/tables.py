# =============================================================================
# outputs/tables.py
# 3 tableaux structurés + export CSV / LaTeX
# =============================================================================

import os
import csv
import io

OUTPUT_DIR_TABLES = os.path.join(
    os.path.dirname(__file__), "..", "outputs_generated", "tables"
)

from data.historical_belgium import FLOOD_EVENTS, AAL_BASELINE
from data.rcp_scenarios import SCENARIOS, TIME_HORIZONS
from models.risk_metrics import (
    compute_risk_table, compute_all_npv, ADAPTATION_MEASURES,
)
from models.vulnerability_model import INSURANCE_PARAMS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_csv(filename: str, rows: list, fieldnames: list):
    path = os.path.join(OUTPUT_DIR_TABLES, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  ✓ CSV : {path}")


def _fmt_meur(val, decimals=0):
    if val is None:
        return "?"
    return f"{val:,.{decimals}f}"


def _fmt_pct(val, decimals=1):
    if val is None:
        return "?"
    return f"{val:.{decimals}f}%"


# ---------------------------------------------------------------------------
# Tableau 1 — Données historiques belges sourcées
# ---------------------------------------------------------------------------

def generate_table1(print_to_console: bool = True, save_csv: bool = True):
    """
    Tableau 1 : Événements historiques d'inondation en Belgique.
    Colonnes : Année | Événement | Pertes totales (M€) | Pertes assurées (M€) | Source

    SOURCE: EM-DAT (CRED/UCLouvain); Assuralia (2021); Swiss Re Sigma
    """
    rows = []
    for evt in FLOOD_EVENTS:
        rows.append({
            "Année":               evt["year"],
            "Mois":                evt["month"],
            "Événement":           evt["event_name"],
            "Décès":               evt["deaths"],
            "Pertes totales (M€)": _fmt_meur(evt["losses_total_MEUR"]),
            "Pertes assurées (M€)":_fmt_meur(evt["losses_insured_MEUR"])
                                    if evt["losses_insured_MEUR"] is not None else "?",
            "Source":              evt["source"],
            "Note":                evt.get("note", ""),
        })

    # Ligne AAL baseline
    rows.append({
        "Année":               "1990–2023",
        "Mois":                "—",
        "Événement":           "AAL historique moyen (estimation)",
        "Décès":               "—",
        "Pertes totales (M€)": f"{AAL_BASELINE['central_MEUR']:.0f} [{AAL_BASELINE['low_MEUR']:.0f}–{AAL_BASELINE['high_MEUR']:.0f}]",
        "Pertes assurées (M€)":f"~{AAL_BASELINE['central_MEUR'] * 0.375:.0f}",
        "Source":              AAL_BASELINE["source"],
        "Note":                "AAL = Pertes Annuelles Moyennes — estimation, pas un événement unique",
    })

    if print_to_console:
        header = f"\n{'='*110}\nTABLEAU 1 — Données historiques inondations Belgique\n{'='*110}"
        print(header)
        print(f"{'Année':<10} {'Événement':<35} {'Total (M€)':<14} {'Assuré (M€)':<14} {'Source'}")
        print("-" * 110)
        for r in rows:
            print(f"{str(r['Année']):<10} {r['Événement']:<35} "
                  f"{r['Pertes totales (M€)']:<14} {r['Pertes assurées (M€)']:<14} "
                  f"{r['Source']}")
        print(f"\nNote : '?' = valeur non documentée dans les sources disponibles")
        print(f"       'ESTIMATED' dans les notes = valeur dérivée, non confirmée directement")

    if save_csv:
        os.makedirs(OUTPUT_DIR_TABLES, exist_ok=True)
        _write_csv("tableau_1_historique.csv", rows, list(rows[0].keys()))

    # Export LaTeX
    _write_latex_table1(rows)
    return rows


def _write_latex_table1(rows):
    path = os.path.join(OUTPUT_DIR_TABLES, "tableau_1_historique_latex.tex")
    with open(path, "w", encoding="utf-8") as f:
        f.write("% Tableau 1 — Données historiques inondations Belgique\n")
        f.write("% Source : EM-DAT/CRED, Assuralia, Swiss Re Sigma\n")
        f.write("\\begin{table}[htbp]\n\\centering\n")
        f.write("\\caption{Événements historiques d'inondation en Belgique "
                "(sources : EM-DAT/CRED, Assuralia, Swiss Re Sigma)}\n")
        f.write("\\label{tab:historique}\n")
        f.write("\\begin{tabular}{lp{4.5cm}rrl}\n\\hline\n")
        f.write("\\textbf{Année} & \\textbf{Événement} & "
                "\\textbf{Total (M€)} & \\textbf{Assuré (M€)} & \\textbf{Source} \\\\\n")
        f.write("\\hline\n")
        for r in rows:
            yr  = str(r["Année"]).replace("–", "--")
            evt = r["Événement"].replace("é", "\\'e").replace("è", "\\`e").replace("â", "\\^a").replace("ô", "\\^o")
            tot = r["Pertes totales (M€)"].replace("?", "\\texttt{?}")
            ins = r["Pertes assurées (M€)"].replace("?", "\\texttt{?}")
            src = r["Source"][:40]
            f.write(f"{yr} & {evt} & {tot} & {ins} & \\footnotesize{{{src}}} \\\\\n")
        f.write("\\hline\n\\end{tabular}\n")
        f.write("\\begin{tablenotes}\\footnotesize\n")
        f.write("\\item \\texttt{?} = valeur non documentée. "
                "ESTIMATED = valeur dérivée. "
                "Source primaire EM-DAT : \\url{https://www.emdat.be}.\n")
        f.write("\\end{tablenotes}\n\\end{table}\n")
    print(f"  ✓ LaTeX : {path}")


# ---------------------------------------------------------------------------
# Tableau 2 — Risk metrics actuariels par scénario × horizon
# ---------------------------------------------------------------------------

def generate_table2(print_to_console: bool = True, save_csv: bool = True):
    """
    Tableau 2 : Métriques actuarielles par scénario et horizon.
    Colonnes : Scénario | Horizon | °C | AAL [IC 90%] | PML-100 | PML-200 |
               Protection gap | SCR Nat-Cat

    SOURCE: Dottori (2018); IPCC AR5 (2014); EIOPA (2014); Swiss Re Sigma (2023)
    """
    risk_rows = compute_risk_table()
    # Filtrer sur les horizons 2050 et 2100 + baseline
    rows_display = [r for r in risk_rows if r["year"] in [2020, 2050, 2100]]

    formatted_rows = []
    for r in rows_display:
        wc = r["warming_C_central"]
        wl = r["warming_C_low"]
        wh = r["warming_C_high"]
        aal_c  = r["aal_c_MEUR"]
        aal_lo = r["aal_lo_MEUR"]
        aal_hi = r["aal_hi_MEUR"]

        formatted_rows.append({
            "Scénario":              r["scenario"],
            "Horizon":               r["year"],
            "°C (médiane [IC 90%])": f"{wc:.1f} [{wl:.1f}–{wh:.1f}]"
                                     if wc > 0 else "0.0 (baseline)",
            "AAL (M€/an) [IC 90%]": f"{aal_c:.0f} [{aal_lo:.0f}–{aal_hi:.0f}]",
            "PML-100 (M€)":          _fmt_meur(r["pml100_MEUR"]),
            "PML-200 (M€)":          _fmt_meur(r["pml200_MEUR"]),
            "Protection gap (%) [dérivé]": _fmt_pct(r["protection_gap_pct"]),
            "SCR Nat-Cat (M€) [approx.]":  _fmt_meur(r["scr_MEUR"]),
            "Source":                r["source"][:80],
        })

    if print_to_console:
        print(f"\n{'='*130}\nTABLEAU 2 — Risk metrics actuariels par scénario et horizon\n{'='*130}")
        print(f"{'Scénario':<12} {'Horizon':<8} {'°C (IC 90%)':<22} "
              f"{'AAL M€/an (IC 90%)':<28} {'PML-100':<12} {'PML-200':<12} "
              f"{'Gap % (dér.)':<12} {'SCR (M€) (approx.)'}")
        print("-" * 130)
        for r in formatted_rows:
            print(f"{r['Scénario']:<12} {str(r['Horizon']):<8} "
                  f"{r['°C (médiane [IC 90%])']:<22} "
                  f"{r['AAL (M€/an) [IC 90%]']:<28} "
                  f"{r['PML-100 (M€)']:<12} {r['PML-200 (M€)']:<12} "
                  f"{r['Protection gap (%) [dérivé]']:<8} {r['SCR Nat-Cat (M€) [approx.]']}")
        print(f"\nNotes :")
        print(f"  - PML = Probable Maximum Loss (pertes à période de retour T ans)")
        print(f"  - SCR = Capital de Solvabilité Requis (APPROXIMATION formule standard EIOPA 2014)")
        print(f"  - Protection gap = part non assurée des pertes économiques totales (dérivé)")
        print(f"  - IC 90% = Intervalle de Confiance 90% sur les projections")
        print(f"  - Sources primaires : Dottori (2018) · IPCC AR5 (2014) · Swiss Re Sigma (2023)")

    if save_csv:
        os.makedirs(OUTPUT_DIR_TABLES, exist_ok=True)
        _write_csv("tableau_2_risk_metrics.csv", formatted_rows, list(formatted_rows[0].keys()))

    _write_latex_table2(formatted_rows)
    return formatted_rows


def _write_latex_table2(rows):
    path = os.path.join(OUTPUT_DIR_TABLES, "tableau_2_risk_metrics_latex.tex")
    with open(path, "w", encoding="utf-8") as f:
        f.write("% Tableau 2 — Risk metrics actuariels\n")
        f.write("% Sources : Dottori (2018); IPCC AR5 (2014); EIOPA (2014); Swiss Re Sigma (2023)\n")
        f.write("\\begin{table}[htbp]\n\\centering\\small\n")
        f.write("\\caption{Risk metrics actuariels par sc\\'enario RCP et horizon temporel "
                "(IC 90\\%; PML en M\\euro; SCR = approximation formule standard EIOPA 2014; "
                "protection gap d\\'eriv\\'e d'un taux assur\\'e 35--40\\% Swiss Re)}\n")
        f.write("\\label{tab:risk_metrics}\n")
        f.write("\\begin{tabular}{llp{2.5cm}p{3.5cm}rrrr}\n\\hline\n")
        f.write("\\textbf{Sc.} & \\textbf{An} & \\textbf{\\Delta T (°C)} & "
                "\\textbf{AAL [IC90\\%]} & \\textbf{PML$_{100}$} & \\textbf{PML$_{200}$} & "
                "\\textbf{Gap\\%$^{*}$} & \\textbf{SCR$^{*}$} \\\\\n\\hline\n")
        for r in rows:
            f.write(
                f"{r['Scénario']} & {r['Horizon']} & {r['°C (médiane [IC 90%])'].replace('[','[').replace('–','--')} & "
                f"{r['AAL (M€/an) [IC 90%]'].replace('–','--')} & "
                f"{r['PML-100 (M€)']} & {r['PML-200 (M€)']} & "
                f"{r['Protection gap (%) [dérivé]']} & {r['SCR Nat-Cat (M€) [approx.]']} \\\\\n"
            )
        f.write("\\hline\n\\end{tabular}\n\\end{table}\n")
    print(f"  ✓ LaTeX : {path}")


# ---------------------------------------------------------------------------
# Tableau 3 — Coût-bénéfice des mesures d'adaptation
# ---------------------------------------------------------------------------

def generate_table3(print_to_console: bool = True, save_csv: bool = True):
    """
    Tableau 3 : Coût-bénéfice des mesures d'adaptation.
    Colonnes : Mesure | Coût (M€) | Réduction RCP4.5 (%) | Réduction RCP8.5 (%) |
               VAN r=3% | B/C ratio | Source

    SOURCE: Alfieri et al. (2016) Climatic Change 136:507-521
    SOURCE: European Commission (2014) Guide to CBA
    """
    all_npv = compute_all_npv()

    # Indexer par (measure_name, scenario, discount)
    npv_index = {
        (r["measure_name"], r["scenario"], r["discount_label"]): r
        for r in all_npv
    }

    rows = []
    for measure in ADAPTATION_MEASURES:
        if measure.get("category") == "transfer":
            continue
        name = measure["name"]
        r45_3 = npv_index.get((name, "RCP4.5-2100", "3%"), {})
        r45_5 = npv_index.get((name, "RCP4.5-2100", "5%"), {})
        r85_3 = npv_index.get((name, "RCP8.5-2100", "3%"), {})

        rows.append({
            "Mesure":                    name,
            "Coût estimé (M€)":          _fmt_meur(measure["cost_MEUR"]),
            "Durée de vie (ans)":         measure["lifetime_years"],
            "Réduction risque RCP4.5 (%)": _fmt_pct(measure["risk_reduction_RCP45_pct"]),
            "Réduction risque RCP8.5 (%)": _fmt_pct(measure["risk_reduction_RCP85_pct"]),
            "VAN r=3% RCP4.5 (M€)":      _fmt_meur(r45_3.get("npv_MEUR")),
            "VAN r=5% RCP4.5 (M€)":      _fmt_meur(r45_5.get("npv_MEUR")),
            "VAN r=3% RCP8.5 (M€)":      _fmt_meur(r85_3.get("npv_MEUR")),
            "B/C ratio (r=3%, RCP4.5)":  f"{r45_3.get('bc_ratio', 0):.1f}×"
                                          if r45_3.get("bc_ratio") is not None else "?",
            "Source coût":               measure["cost_source"][:60],
            "Source B/C":                measure["bc_ratio_source"][:60],
            "Note":                      measure["note"],
        })

    if print_to_console:
        print(f"\n{'='*140}\nTABLEAU 3 — Analyse Coût-Bénéfice des Mesures d'Adaptation\n{'='*140}")
        print(f"{'Mesure':<30} {'Coût (M€)':<12} {'RCP4.5 %':<12} {'RCP8.5 %':<12} "
              f"{'VAN r=3% RCP4.5':<18} {'VAN r=3% RCP8.5':<18} {'B/C (r=3%)'}")
        print("-" * 140)
        for r in rows:
            print(f"{r['Mesure']:<30} {r['Coût estimé (M€)']:<12} "
                  f"{r['Réduction risque RCP4.5 (%)']:<12} "
                  f"{r['Réduction risque RCP8.5 (%)']:<12} "
                  f"{r['VAN r=3% RCP4.5 (M€)']:<18} "
                  f"{r['VAN r=3% RCP8.5 (M€)']:<18} "
                  f"{r['B/C ratio (r=3%, RCP4.5)']}")
        print(f"\nNotes :")
        print(f"  - VAN = Valeur Actuelle Nette sur la durée de vie de la mesure")
        print(f"  - B/C = ratio Bénéfice / Coût (>1 = rentable)")
        print(f"  - r = taux d'actualisation (CE 2014 recommande 3% pour projets environnementaux)")
        print(f"  - B/C issus du modèle (AAL × réduction) — ordres de grandeur Alfieri et al. (2016)")
        print(f"  - L'assurance paramétrique (transfert) est exclue du tableau d'adaptation")
        print(f"  - Co-bénéfices non monétisés (biodiversité, carbone) = B/C sous-estimé")

    if save_csv:
        os.makedirs(OUTPUT_DIR_TABLES, exist_ok=True)
        _write_csv("tableau_3_cout_benefice.csv", rows, list(rows[0].keys()))

    _write_latex_table3(rows)
    return rows


def _write_latex_table3(rows):
    path = os.path.join(OUTPUT_DIR_TABLES, "tableau_3_adaptation_latex.tex")
    with open(path, "w", encoding="utf-8") as f:
        f.write("% Tableau 3 — Coût-Bénéfice des mesures d'adaptation\n")
        f.write("% Sources : Alfieri et al. (2016); CE (2014) Guide CBA\n")
        f.write("\\begin{table}[htbp]\n\\centering\\small\n")
        f.write("\\caption{Analyse co\\^ut-b\\'en\\'efice des mesures d'adaptation "
                "(Alfieri et al. 2016; taux actualisation CE 2014)}\n")
        f.write("\\label{tab:adaptation}\n")
        f.write("\\begin{tabular}{p{3cm}rrlrrrl}\n\\hline\n")
        f.write("\\textbf{Mesure} & \\textbf{Co\\^ut} & \\textbf{Dur\\'ee} & "
                "\\textbf{Réd. RCP4.5} & \\textbf{VAN\\,3\\%} & "
                "\\textbf{VAN\\,5\\%} & \\textbf{B/C} & \\textbf{Note} \\\\\n")
        f.write(" & (M\\euro) & (ans) & (\\%) & (M\\euro) & (M\\euro) & & \\\\\n\\hline\n")
        for r in rows:
            name = r["Mesure"][:28]
            note = r["Note"][:35].replace("%", "\\%")
            f.write(
                f"{name} & {r['Coût estimé (M€)']} & {r['Durée de vie (ans)']} & "
                f"{r['Réduction risque RCP4.5 (%)']} & "
                f"{r['VAN r=3% RCP4.5 (M€)']} & {r['VAN r=5% RCP4.5 (M€)']} & "
                f"{r['B/C ratio (r=3%, RCP4.5)']} & \\footnotesize{{{note}}} \\\\\n"
            )
        f.write("\\hline\n\\end{tabular}\n\\end{table}\n")
    print(f"  ✓ LaTeX : {path}")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def generate_all_tables():
    """Génère les 3 tableaux (CSV + LaTeX) et les affiche dans le terminal."""
    print("\n--- Génération des tableaux ---")
    os.makedirs(OUTPUT_DIR_TABLES, exist_ok=True)
    t1 = generate_table1()
    t2 = generate_table2()
    t3 = generate_table3()
    print("  → 3 tableaux générés (CSV + LaTeX).")
    return {"t1": t1, "t2": t2, "t3": t3}
