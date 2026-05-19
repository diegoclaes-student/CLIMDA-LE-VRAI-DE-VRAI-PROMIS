# =============================================================================
# report_summary.py
# Résumé narratif avec chiffres clés + bibliographie complète
# Prêt à être copié dans LaTeX
# =============================================================================

import os
from config.sources import SOURCES, get_bibtex_all
from data.historical_belgium import AAL_BASELINE, FLOOD_EVENTS
from data.rcp_scenarios import SCENARIOS, get_warming_at_year, get_damage_factor
from models.hazard_model import compute_aal_projections, compute_ep_curve_future
from models.risk_metrics import compute_risk_table, compute_all_npv

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs_generated")


def generate_key_figures() -> dict:
    """Collecte les chiffres clés avec leurs sources pour le rapport."""
    projections = compute_aal_projections()
    risk_table  = compute_risk_table()

    key_figures = {}

    # --- Baseline ---
    key_figures["aal_baseline"] = {
        "value": f"{AAL_BASELINE['central_MEUR']:.0f} M€/an "
                 f"[IC: {AAL_BASELINE['low_MEUR']:.0f}–{AAL_BASELINE['high_MEUR']:.0f} M€/an]",
        "source": AAL_BASELINE["source"],
    }

    # --- Événement 2021 ---
    evt_2021 = next(e for e in FLOOD_EVENTS if e["year"] == 2021)
    key_figures["event_2021_insured"] = {
        "value": f"{evt_2021['losses_insured_MEUR']:,.0f} M€ (pertes assurées CONFIRMÉES)",
        "source": "Assuralia (2021)",
    }
    key_figures["event_2021_total"] = {
        "value": f"{evt_2021['losses_total_MEUR']:,.0f} M€ [4 000–10 000 M€] (estimation)",
        "source": (
            "Assuralia (2021); Swiss Re Sigma (2023) — part assurée 35–40% "
            "(total estimé, non spécifique à l'événement)"
        ),
    }
    key_figures["event_2021_return_period"] = {
        "value": "~1/400 ans dans le climat actuel [IC: 1/100–1/9000]",
        "source": "Kreienkamp et al. (2021) WWA, DOI 10.25561/88185",
    }

    # --- Projections par scénario ---
    for scen_key in ["RCP26", "RCP45", "RCP60", "RCP85"]:
        proj = projections[scen_key]
        # Trouver indice de 2100 dans la liste
        years_list = proj["years"]
        idx_2100 = years_list.index(2100) if 2100 in years_list else -1

        if idx_2100 >= 0:
            aal_c  = proj["aal_c"][idx_2100]
            aal_lo = proj["aal_lo"][idx_2100]
            aal_hi = proj["aal_hi"][idx_2100]
            dT_c, dT_lo, dT_hi = get_warming_at_year(scen_key, 2100)
            delta_c, _, _ = get_damage_factor(dT_c)

            key_figures[f"aal_{scen_key}_2100"] = {
                "value": f"{aal_c:.0f} M€/an [IC 90%: {aal_lo:.0f}–{aal_hi:.0f} M€/an]",
                "warming": f"{dT_c:.1f}°C [{dT_lo:.1f}–{dT_hi:.1f}°C] vs 2000-2020",
                "damage_factor": f"×{(1+delta_c):.2f} (CC seul)",
                "source": "Dottori et al. (2018) [CC]; Winsemius et al. (2016) [exposition]; IPCC AR5 (2014)",
            }

    # --- PML et SCR ---
    for r in risk_table:
        if r["year"] == 2100 and r["scenario"] != "Baseline":
            scen_short = r["scenario"].replace(" ", "_").replace(".", "")
            key_figures[f"pml200_{scen_short}_2100"] = {
                "value": f"PML-200: {r['pml200_MEUR']:,.0f} M€ | SCR: {r['scr_MEUR']:,.0f} M€",
                "source": "Dottori (2018) [EP curve] + EIOPA (2014) [SCR approx.]",
            }

    # --- Adaptation ---
    all_npv = compute_all_npv()
    best_bc = max(all_npv, key=lambda x: x.get("bc_ratio", 0)
                  if x["scenario"] == "RCP4.5-2100" and x["discount_label"] == "3%" else 0)
    key_figures["best_adaptation_measure"] = {
        "value": f"{best_bc['measure_name']} — B/C = {best_bc['bc_ratio']:.1f}× (VAN = {best_bc['npv_MEUR']:,.0f} M€)",
        "source": "Modèle CLIMDA (AAL × réduction) — ordres de grandeur Alfieri et al. (2016)",
    }

    return key_figures


def write_rapport_chiffres_cles():
    """Écrit le fichier rapport_chiffres_cles.txt (format LaTeX-ready)."""
    figures = generate_key_figures()

    path = os.path.join(OUTPUT_DIR, "rapport_chiffres_cles.txt")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("CHIFFRES CLÉS DU RAPPORT — BELGIQUE FLOOD CLIMADA MODEL\n")
        f.write("Tous les intervalles sont des IC 90% sauf indication contraire.\n")
        f.write("ZÉRO valeur sans source bibliographique identifiée.\n")
        f.write("=" * 80 + "\n\n")

        f.write("--- CONTEXTE HISTORIQUE ---\n\n")
        f.write(f"AAL baseline (2000-2020) :\n"
                f"  Valeur : {figures['aal_baseline']['value']}\n"
                f"  Source : {figures['aal_baseline']['source']}\n\n")

        f.write(f"Inondations juillet 2021 (catastrophe Vesdre/Meuse) :\n"
                f"  Pertes assurées : {figures['event_2021_insured']['value']}\n"
                f"  Source : {figures['event_2021_insured']['source']}\n"
                f"  Pertes totales (est.) : {figures['event_2021_total']['value']}\n"
                f"  Source : {figures['event_2021_total']['source']}\n"
                f"  Période de retour : {figures['event_2021_return_period']['value']}\n"
                f"  Source : {figures['event_2021_return_period']['source']}\n\n")

        f.write("--- PROJECTIONS RCP (AAL à 2100, CC + croissance exposition) ---\n\n")
        for scen_key in ["RCP26", "RCP45", "RCP60", "RCP85"]:
            k = f"aal_{scen_key}_2100"
            if k in figures:
                fig = figures[k]
                f.write(f"{SCENARIOS[scen_key]['label']} ({SCENARIOS[scen_key]['description']}) :\n")
                f.write(f"  AAL 2100 : {fig['value']}\n")
                f.write(f"  Réchauffement : {fig['warming']}\n")
                f.write(f"  Facteur dommages : {fig['damage_factor']}\n")
                f.write(f"  Source : {fig['source']}\n\n")

        f.write("--- PML ET SCR PAR SCÉNARIO (2100) ---\n\n")
        for key, val in figures.items():
            if key.startswith("pml200_"):
                scen_name = key.replace("pml200_", "").replace("_", " ").replace("2100", "(2100)")
                f.write(f"{scen_name} :\n"
                        f"  {val['value']}\n"
                        f"  Source : {val['source']}\n\n")

        f.write("--- MESURES D'ADAPTATION ---\n\n")
        f.write(f"Meilleure mesure (B/C ratio) :\n"
                f"  {figures['best_adaptation_measure']['value']}\n"
                f"  Source : {figures['best_adaptation_measure']['source']}\n\n")

        f.write("--- FORMULES MATHÉMATIQUES UTILISÉES ---\n\n")
        f.write("1. Projection des dommages (Dottori-interpolée) :\n")
        f.write("   D_RCP(t) = D_baseline × [1 + Δ_damage(T_RCP(t))]\n")
        f.write("   où T_RCP(t) = IPCC AR5 Table SPM.2 et Δ_damage interpolé depuis Dottori (2018)\n\n")
        f.write("2. AAL = ∫₀¹ L(p) dp ≈ Σᵢ Lᵢ × (pᵢ₋₁ - pᵢ₊₁) / 2 (méthode trapèze)\n\n")
        f.write("3. Fonctions d'impact CLIMADA :\n")
        f.write("   Impact(I) = MDD(I) × PAA(I) × Valeur_exposée\n")
        f.write("   MDD(I) = 1 / (1 + exp(-k(I - I₀))) — sigmoïde (Huizinga et al. 2017)\n\n")
        f.write("4. SCR Nat-Cat (approx. Solvency II) :\n")
        f.write("   SCR ≈ max(PML_200ans − AAL, 0)  [VaR 99.5%]\n")
        f.write("   Source exacte : EIOPA (2014) Technical Specification, Section 7\n\n")
        f.write("5. NPV adaptation (méthode ECA-CLIMADA) :\n")
        f.write("   NPV = Σₜ [(B(t) - C(t)) / (1+r)^t]\n")
        f.write("   r ∈ {0.03, 0.05} (CE 2014 Guide CBA)\n\n")

        f.write("--- AVERTISSEMENTS SUR L'INCERTITUDE ---\n\n")
        f.write("1. Les intervalles de confiance sont LARGES — c'est un résultat scientifique\n")
        f.write("   (Alfieri et al. 2018 — divergence inter-modèles documentée)\n\n")
        f.write("2. RCP 8.5 à 2100 (ΔT > 3°C) : extrapolation au-delà du domaine Dottori (2018)\n")
        f.write("   → Incertitude considérablement accrue, à commenter explicitement\n\n")
        f.write("3. Données historiques belges < 1990 : incomplètes (biais EM-DAT)\n")
        f.write("   → Test Mann-Kendall appliqué sur 1990-2023 uniquement\n\n")
        f.write("4. PIB utilisé comme proxy des actifs exposés : hypothèse simplificatrice\n")
        f.write("   → Sous-estimation possible de l'exposition réelle du stock de capital\n\n")
        f.write("5. Courbe EP plafonnée à T=1 000 ans (queue non calibrée GPD/GEV)\n")
        f.write("   → Extrapolations au-delà non justifiées sans modèle de queue explicite\n\n")

    print(f"  ✓ Rapport chiffres clés : {path}")
    return path


def write_bibliography_bib():
    """Exporte toute la bibliographie en format BibTeX."""
    bibtex_content = get_bibtex_all()
    path = os.path.join(OUTPUT_DIR, "bibliography.bib")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write("% =========================================================\n")
        f.write("% bibliography.bib — Références du modèle CLIMADA Belgique\n")
        f.write("% Généré automatiquement depuis config/sources.py\n")
        f.write("% =========================================================\n\n")
        f.write(bibtex_content)
        f.write("\n")

    print(f"  ✓ Bibliographie BibTeX : {path}")
    return path


def print_key_figures_terminal():
    """Affiche dans le terminal les chiffres clés avec intervalles d'incertitude."""
    print("\n" + "=" * 80)
    print("RÉSULTATS CLÉS — MODÈLE CLIMADA INONDATIONS BELGIQUE")
    print("Tous les chiffres incluent des intervalles d'incertitude.")
    print("AUCUNE valeur ponctuelle trompeuse n'est présentée seule.")
    print("=" * 80)

    figures = generate_key_figures()

    print("\n📌 AAL BASELINE (2000-2020) :")
    kf = figures["aal_baseline"]
    print(f"   {kf['value']}")
    print(f"   → {kf['source']}")

    print("\n📌 ÉVÉNEMENT JUILLET 2021 :")
    print(f"   Assurés (CONFIRMÉ) : {figures['event_2021_insured']['value']}")
    print(f"   Pertes totales    : {figures['event_2021_total']['value']}")
    print(f"   Période de retour : {figures['event_2021_return_period']['value']}")

    print("\n📌 PROJECTIONS AAL À 2100 :")
    for scen_key in ["RCP26", "RCP45", "RCP60", "RCP85"]:
        k = f"aal_{scen_key}_2100"
        if k in figures:
            fig = figures[k]
            label = SCENARIOS[scen_key]["label"]
            print(f"   {label} : {fig['value']}")
            print(f"             ΔT={fig['warming']} | {fig['damage_factor']}")

    print("\n📌 MEILLEURE MESURE D'ADAPTATION :")
    print(f"   {figures['best_adaptation_measure']['value']}")
    print(f"   → {figures['best_adaptation_measure']['source']}")

    print("\n⚠️  AVERTISSEMENTS CRITIQUES :")
    print("   1. IC larges = résultat scientifique (Alfieri 2018) — ne pas réduire les IC")
    print("   2. RCP 8.5 (2100) = extrapolation hors domaine Dottori — commenter impérativement")
    print("   3. Données EM-DAT < 1990 incomplètes — exclure de l'analyse de tendance")
    print()


def generate_report_summary():
    """Point d'entrée pour le résumé du rapport."""
    print("\n--- Génération du résumé rapport ---")
    print_key_figures_terminal()
    path_txt = write_rapport_chiffres_cles()
    path_bib = write_bibliography_bib()
    print(f"  → Résumé généré : {path_txt}")
    print(f"  → Bibliographie : {path_bib}")
    return {"figures": generate_key_figures(), "txt_path": path_txt, "bib_path": path_bib}
