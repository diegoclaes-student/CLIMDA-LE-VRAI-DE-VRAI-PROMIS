#!/usr/bin/env python3
# =============================================================================
# main.py — Script principal du modèle CLIMADA Belgique Inondations
#
# Usage : python main.py [--maps] [--charts] [--tables] [--summary] [--all]
#
# Décomposition CLIMADA :
#   Risque = Aléa (Hazard) × Exposition × Vulnérabilité
#
# Sources principales :
#   - Dottori et al. (2018) Nat. Clim. Change 8:781-786  [dommages RCP]
#   - IPCC AR5 (2014) Table SPM.2                         [réchauffement RCP]
#   - Alfieri et al. (2015, 2016, 2018)                   [Q100, adaptation, incertitude]
#   - Kreienkamp et al. (2021) WWA DOI 10.25561/88185     [calibration EP]
#   - Swiss Re Sigma (2023)                               [AAL baseline]
#   - Assuralia (2021)                                    [pertes 2021 confirmées]
#   - Eurostat (2022)                                     [PIB Belgique]
#   - EIOPA (2014)                                        [SCR Solvency II]
# =============================================================================

import sys
import os
import time
import argparse
import warnings

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# Assurer que le répertoire du projet est dans le path Python
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def print_header():
    print("\n" + "=" * 78)
    print("  CLIMADA BELGIUM FLOOD RISK MODEL")
    print("  Cours LACTU2000 — UCLouvain — Risques émergents et enjeux de société")
    print("  Cadre : Dottori et al. (2018) + IPCC AR5 (2014) + Alfieri et al.")
    print("=" * 78)
    print()
    print("  ZÉRO valeur numérique sans source bibliographique — règle absolue.")
    print("  Tous les résultats incluent des intervalles de confiance.")
    print()


def check_dependencies():
    """Vérifie les dépendances et affiche les avertissements."""
    print("--- Vérification des dépendances ---")
    deps = {
        "numpy":      "REQUIS",
        "matplotlib": "REQUIS",
        "scipy":      "RECOMMANDÉ (test Mann-Kendall)",
        "pandas":     "RECOMMANDÉ (export CSV)",
        "geopandas":  "OPTIONNEL (cartes précises — fallback sur bulles matplotlib)",
        "statsmodels":"OPTIONNEL (analyses statistiques supplémentaires)",
        "rasterio":   "OPTIONNEL (pipeline JRC hazard)",
        "shapely":    "OPTIONNEL (pipeline JRC hazard)",
        "pyarrow":    "OPTIONNEL (export Parquet JRC)",
    }
    all_ok = True
    for pkg, requirement in deps.items():
        try:
            __import__(pkg)
            status = "✓"
        except ImportError:
            status = "✗"
            if "REQUIS" in requirement:
                all_ok = False
                print(f"  {status} {pkg:<15} {requirement} — MANQUANT (pip install {pkg})")
            else:
                print(f"  {status} {pkg:<15} {requirement} — non installé (optionnel)")
            continue
        print(f"  {status} {pkg:<15} {requirement}")

    if not all_ok:
        print("\n  ERREUR : Dépendances requises manquantes. Installer avec:")
        print("  pip install numpy matplotlib scipy\n")
        sys.exit(1)
    print()


def run_validation():
    """Validation rapide des paramètres et de la cohérence des données."""
    print("--- Validation des paramètres ---")

    from data.historical_belgium import AAL_BASELINE, EP_POWER_LAW_PARAMS
    from data.rcp_scenarios import get_warming_at_year, get_damage_factor

    # Test cohérence AAL
    alpha = EP_POWER_LAW_PARAMS["alpha"]
    x_min = EP_POWER_LAW_PARAMS["x_min"]
    aal_analytic = x_min / (alpha - 1)
    aal_central = AAL_BASELINE["central_MEUR"]
    assert 150 <= aal_analytic <= 280, f"AAL analytique hors plage: {aal_analytic:.0f}"
    print(f"  ✓ AAL analytique = {aal_analytic:.0f} M€/an (plage Swiss Re: 165-275 M€)")

    # Test facteurs Dottori
    delta_15, _, _ = get_damage_factor(1.5)
    assert abs(delta_15 - 1.13) < 0.01, f"Facteur Dottori 1.5°C incorrect: {delta_15}"
    delta_30, _, _ = get_damage_factor(3.0)
    assert abs(delta_30 - 1.45) < 0.01, f"Facteur Dottori 3.0°C incorrect: {delta_30}"
    print(f"  ✓ Facteurs Dottori : +1.5°C → +{delta_15*100:.0f}%, +3.0°C → +{delta_30*100:.0f}%")
    print(f"    (valeurs confirmées : Dottori et al. 2018, Nat. Clim. Change 8:781-786)")

    # Test réchauffement IPCC AR5
    dT_45, _, _ = get_warming_at_year("RCP45", 2100)
    assert abs(dT_45 - 1.8) < 0.01, f"Réchauffement RCP 4.5 incorrect: {dT_45}"
    dT_85, _, _ = get_warming_at_year("RCP85", 2100)
    assert abs(dT_85 - 3.7) < 0.01, f"Réchauffement RCP 8.5 incorrect: {dT_85}"
    print(f"  ✓ Réchauffement IPCC AR5 : RCP4.5={dT_45}°C, RCP8.5={dT_85}°C à 2100")
    print(f"    (source : IPCC AR5 2014, Table SPM.2)")

    # Test EP calibration
    from models.hazard_model import compute_ep_curve_baseline
    import numpy as np
    ep = compute_ep_curve_baseline(np.array([400.0]))
    l400 = ep["losses_MEUR"][0]
    assert 4000 <= l400 <= 8000, f"Calibration EP T=400 hors plage: {l400:.0f} M€"
    print(f"  ✓ Calibration EP : T=400 → {l400:.0f} M€ [cible: ~6000 M€, Kreienkamp 2021]")

    print()


def compute_pml_from_ep(ep, T):
    """Helper pour les tests — PML à la période de retour T."""
    import numpy as np
    return float(np.interp(T, ep["return_periods"][::-1], ep["losses_MEUR"][::-1]))


def run_all():
    """Exécute l'ensemble du pipeline."""
    print_header()
    check_dependencies()
    run_validation()

    t0 = time.time()
    os.makedirs(os.path.join(project_root, "outputs_generated", "figures"), exist_ok=True)
    os.makedirs(os.path.join(project_root, "outputs_generated", "tables"), exist_ok=True)

    # --- 1. Résumé rapport ---
    from report_summary import generate_report_summary
    generate_report_summary()

    # --- 2. Tableaux ---
    from outputs.tables import generate_all_tables
    generate_all_tables()

    # --- 3. Cartes ---
    from outputs.maps import generate_all_maps
    generate_all_maps()

    # --- 4. Graphiques ---
    from outputs.charts import generate_all_charts
    generate_all_charts()

    elapsed = time.time() - t0
    print(f"\n{'='*78}")
    print(f"  Pipeline terminé en {elapsed:.1f}s")
    print(f"  Sorties dans : {os.path.join(project_root, 'outputs_generated/')}")
    print(f"  - figures/  : 4 cartes + 6 graphiques (300 DPI)")
    print(f"  - tables/   : 3 tableaux (CSV + LaTeX)")
    print(f"  - bibliography.bib     : références BibTeX complètes")
    print(f"  - rapport_chiffres_cles.txt : chiffres pour LaTeX")
    print(f"{'='*78}\n")


def main():
    parser = argparse.ArgumentParser(
        description="CLIMADA Belgium Flood Risk Model — UCLouvain LACTU2000",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
    Exemples :
      python main.py --all           # tout générer
      python main.py --summary       # résumé + bibliographie uniquement
      python main.py --tables        # tableaux uniquement
      python main.py --charts        # graphiques uniquement
      python main.py --maps          # cartes uniquement
      python main.py --jrc           # pipeline raster JRC (hazard)
        """,
    )
    parser.add_argument("--all",     action="store_true", help="Générer tous les outputs")
    parser.add_argument("--maps",    action="store_true", help="Cartes géographiques (A, B, C, D)")
    parser.add_argument("--charts",  action="store_true", help="Graphiques analytiques (1–6)")
    parser.add_argument("--tables",  action="store_true", help="Tableaux (1–3) + CSV + LaTeX")
    parser.add_argument("--summary", action="store_true", help="Résumé rapport + bibliographie BibTeX")
    parser.add_argument("--validate",action="store_true", help="Validation des paramètres uniquement")
    parser.add_argument("--jrc",     action="store_true", help="Pipeline raster JRC (aléa inondation)")

    args = parser.parse_args()

    # Par défaut, tout générer
    if not any(vars(args).values()):
        args.all = True

    print_header()
    check_dependencies()

    if args.validate or args.all:
        run_validation()

    if args.all:
        run_all()
        return

    if args.jrc:
        from data.jrc_hazard_pipeline import run_jrc_pipeline
        run_jrc_pipeline()
        return

    os.makedirs(os.path.join(project_root, "outputs_generated", "figures"), exist_ok=True)
    os.makedirs(os.path.join(project_root, "outputs_generated", "tables"), exist_ok=True)

    if args.summary:
        from report_summary import generate_report_summary
        generate_report_summary()

    if args.tables:
        from outputs.tables import generate_all_tables
        generate_all_tables()

    if args.maps:
        from outputs.maps import generate_all_maps
        generate_all_maps()

    if args.charts:
        from outputs.charts import generate_all_charts
        generate_all_charts()


if __name__ == "__main__":
    main()
