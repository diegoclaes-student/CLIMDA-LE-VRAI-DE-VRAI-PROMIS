# =============================================================================
# config/sources.py
# Dictionnaire centralisé de toutes les sources bibliographiques du projet.
# Ce fichier est la référence unique — tout le code doit y renvoyer.
# =============================================================================

SOURCES = {

    # -------------------------------------------------------------------------
    # PROJECTIONS DE DOMMAGES / RISQUE CLIMATIQUE — EUROPE
    # -------------------------------------------------------------------------
    "dottori2018": {
        "key": "dottori2018",
        "authors": "Dottori, F., Szewczyk, W., Ciscar, J.-C., Zhao, F., Alfieri, L., "
                   "Hirabayashi, Y., Bianchi, A., Mongelli, I., Frieler, K., Betts, R.A., Feyen, L.",
        "year": 2018,
        "title": "Increased human and economic losses from river flooding with anthropogenic warming",
        "journal": "Nature Climate Change",
        "volume": 8,
        "pages": "781–786",
        "doi": "10.1038/s41558-018-0257-z",
        "key_values": {
            # Augmentation des dommages économiques vs baseline historique
            # pour l'Europe Centrale et Occidentale (dont Belgique)
            # Table 1 et Fig. 2 de l'article
            "damage_increase_1p5C_pct": 113.0,   # +113 % à +1.5°C (moyenne Europe)
            "damage_increase_2p0C_pct": 131.0,   # +131 % à +2.0°C (interpolé Fig.2)
            "damage_increase_3p0C_pct": 145.0,   # +145 % à +3.0°C (moyenne Europe)
            # Incertitude (range ± approximatif, Supplementary Table S1)
            "damage_increase_1p5C_low":  60.0,   # borne basse 90% IC
            "damage_increase_1p5C_high": 180.0,  # borne haute 90% IC
            "damage_increase_3p0C_low":  85.0,
            "damage_increase_3p0C_high": 220.0,
            # Population affectée
            "pop_affected_increase_1p5C_pct": 86.0,
            "pop_affected_increase_3p0C_pct": 123.0,
        },
        "bibtex": (
            "@article{dottori2018,\n"
            "  author  = {Dottori, Francesco and Szewczyk, Wojciech and Ciscar, Juan-Carlos\n"
            "             and Zhao, Fang and Alfieri, Lorenzo and Hirabayashi, Yukiko\n"
            "             and Bianchi, Alessandra and Mongelli, Ignazio and Frieler, Katja\n"
            "             and Betts, Richard A. and Feyen, Luc},\n"
            "  title   = {Increased human and economic losses from river flooding with\n"
            "             anthropogenic warming},\n"
            "  journal = {Nature Climate Change},\n"
            "  volume  = {8},\n"
            "  pages   = {781--786},\n"
            "  year    = {2018},\n"
            "  doi     = {10.1038/s41558-018-0257-z}\n"
            "}"
        ),
    },

    "alfieri2018": {
        "key": "alfieri2018",
        "authors": "Alfieri, L., Dottori, F., Betts, R., Salamon, P., Feyen, L.",
        "year": 2018,
        "title": "Multi-Model Projections of River Flood Risk in Europe under Global Warming",
        "journal": "Climate",
        "volume": 6,
        "issue": 1,
        "pages": "6",
        "doi": "10.3390/cli6010006",
        "key_values": {
            # Comparaison de 3 ensembles de modèles pour l'Europe
            # Résultats pour Western/Central Europe — cohérents avec Dottori 2018
            "model_agreement_direction": "consistently_increasing",
            "uncertainty_range_note": "Large spread across models — key scientific result",
        },
        "bibtex": (
            "@article{alfieri2018,\n"
            "  author  = {Alfieri, Lorenzo and Dottori, Francesco and Betts, Richard\n"
            "             and Salamon, Peter and Feyen, Luc},\n"
            "  title   = {Multi-Model Projections of River Flood Risk in Europe under\n"
            "             Global Warming},\n"
            "  journal = {Climate},\n"
            "  volume  = {6},\n"
            "  number  = {1},\n"
            "  pages   = {6},\n"
            "  year    = {2018},\n"
            "  doi     = {10.3390/cli6010006}\n"
            "}"
        ),
    },

    "alfieri2015": {
        "key": "alfieri2015",
        "authors": "Alfieri, L., Feyen, L., Dottori, F., Bianchi, A.",
        "year": 2015,
        "title": "Ensemble flood risk assessment in Europe under high end climate scenarios",
        "journal": "Global Environmental Change",
        "volume": 35,
        "pages": "199–212",
        "doi": "10.1016/j.gloenvcha.2015.09.004",
        "key_values": {
            # Q100 (débit centennal) — augmentation relative entre 1990 et 2020
            # sous RCP 8.5, par région / Fig. 3 de l'article
            "Q100_increase_pct_min": 18.0,   # minimum tous pays
            "Q100_increase_pct_max": 256.0,  # maximum tous pays
            # Belgique / Europe de l'Ouest — tendance vers le haut
            "Q100_western_europe_central_pct": 50.0,  # estimation médiane Fig. 3
        },
        "bibtex": (
            "@article{alfieri2015,\n"
            "  author  = {Alfieri, Lorenzo and Feyen, Luc and Dottori, Francesco\n"
            "             and Bianchi, Alessandra},\n"
            "  title   = {Ensemble flood risk assessment in Europe under high end\n"
            "             climate scenarios},\n"
            "  journal = {Global Environmental Change},\n"
            "  volume  = {35},\n"
            "  pages   = {199--212},\n"
            "  year    = {2015},\n"
            "  doi     = {10.1016/j.gloenvcha.2015.09.004}\n"
            "}"
        ),
    },

    "alfieri2016": {
        "key": "alfieri2016",
        "authors": "Alfieri, L., Feyen, L., Di Baldassarre, G.",
        "year": 2016,
        "title": "Increasing flood risk under climate change: a pan-European assessment "
                 "of the benefits of four adaptation strategies",
        "journal": "Climatic Change",
        "volume": 136,
        "pages": "507–521",
        "doi": "10.1007/s10584-016-1641-1",
        "key_values": {
            # Bénéfices des mesures d'adaptation — méthode ECA-CLIMADA
            # Table 3 de l'article (benefit-cost ratios)
            "dike_upgrade_bc_ratio_rcp45": 4.2,
            "early_warning_bc_ratio_rcp45": 12.0,  # systèmes d'alerte précoce
            "flood_plains_bc_ratio_rcp45": 2.8,
            "adaptation_discount_rate_pct": 3.0,    # recommandation CE
        },
        "bibtex": (
            "@article{alfieri2016,\n"
            "  author  = {Alfieri, Lorenzo and Feyen, Luc and Di Baldassarre, Giuliano},\n"
            "  title   = {Increasing flood risk under climate change: a pan-European\n"
            "             assessment of the benefits of four adaptation strategies},\n"
            "  journal = {Climatic Change},\n"
            "  volume  = {136},\n"
            "  pages   = {507--521},\n"
            "  year    = {2016},\n"
            "  doi     = {10.1007/s10584-016-1641-1}\n"
            "}"
        ),
    },

    # -------------------------------------------------------------------------
    # DONNEES GEO / ALEA JRC COPERNICUS
    # -------------------------------------------------------------------------
    "jrc_flood_hazard_v3_1_1": {
        "key": "jrc_flood_hazard_v3_1_1",
        "authors": "JRC Copernicus (CEMS/EFAS)",
        "year": 2021,
        "title": "River flood hazard maps for Europe and the Mediterranean Basin region (v3.1.1)",
        "publisher": "European Commission Joint Research Centre",
        "url": "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/",
        "note": "GeoTIFFs at 3 arc-second (~90 m), WGS84 EPSG:4326.",
    },
    "gadm_4_1": {
        "key": "gadm_4_1",
        "authors": "GADM",
        "year": 2022,
        "title": "GADM database of Global Administrative Areas (v4.1)",
        "publisher": "GADM",
        "url": "https://gadm.org/",
        "note": "Boundaries for provinces (ADM1) and communes (ADM3), Belgium.",
    },
    "hydrobasins_v1c": {
        "key": "hydrobasins_v1c",
        "authors": "Lehner, B., Grill, G.",
        "year": 2013,
        "title": "HydroBASINS (HydroSHEDS) v1c",
        "publisher": "World Wildlife Fund",
        "url": "https://www.hydrosheds.org/products/hydrobasins",
        "note": "Level 6 basins used for Meuse/Escaut delineation (EU subset).",
    },

    # -------------------------------------------------------------------------
    # ATTRIBUTION ET ÉVÉNEMENTS EXTRÊMES
    # -------------------------------------------------------------------------
    "kreienkamp2021": {
        "key": "kreienkamp2021",
        "authors": "Kreienkamp, F. et al. (World Weather Attribution consortium)",
        "year": 2021,
        "title": "Rapid attribution of heavy rainfall events leading to the severe "
                 "flooding in Western Europe during July 2021",
        "journal": "World Weather Attribution",
        "doi": "10.25561/88185",
        "key_values": {
            # Période de retour de l'événement de juillet 2021 en Europe de l'Ouest
            # dans le CLIMAT ACTUEL (~+1.2°C au-dessus du pré-industriel)
            "return_period_current_climate_yrs": 400,   # ~1/400 ans
            "return_period_lower_bound_yrs": 100,        # borne basse IC
            "return_period_upper_bound_yrs": 9000,       # borne haute IC (très large)
            # Augmentation de l'intensité des précipitations due au CC
            "precip_intensity_increase_pct": 19.0,      # jusqu'à +19% pour P1-2 jours
            "precip_intensity_increase_low_pct": 3.0,
            "precip_intensity_increase_high_pct": 19.0,
            # Probabilité relative à +2°C
            "frequency_multiplier_at_2C": 1.4,           # 1.4× plus probable
            "frequency_multiplier_at_2C_low": 1.2,
            "frequency_multiplier_at_2C_high": 1.9,
        },
        "bibtex": (
            "@techreport{kreienkamp2021,\n"
            "  author      = {Kreienkamp, Frank and others},\n"
            "  title       = {Rapid attribution of heavy rainfall events leading to the\n"
            "                 severe flooding in {Western Europe} during {July 2021}},\n"
            "  institution = {World Weather Attribution},\n"
            "  year        = {2021},\n"
            "  doi         = {10.25561/88185}\n"
            "}"
        ),
    },

    # -------------------------------------------------------------------------
    # SCÉNARIOS IPCC / RCP
    # -------------------------------------------------------------------------
    "ipcc_ar5_2014": {
        "key": "ipcc_ar5_2014",
        "authors": "IPCC",
        "year": 2014,
        "title": "Climate Change 2014: Synthesis Report. Contribution of Working Groups I, "
                 "II and III to the Fifth Assessment Report",
        "publisher": "IPCC, Geneva",
        "isbn": "978-92-9169-143-2",
        "key_values": {
            # Table SPM.2 — Réchauffement global à 2100 vs 1986-2005 (baseline IPCC AR5)
            # Valeurs médianes et intervalles [5-95%]
            "RCP26_median_C": 1.0,   "RCP26_low_C": 0.3,  "RCP26_high_C": 1.7,
            "RCP45_median_C": 1.8,   "RCP45_low_C": 1.1,  "RCP45_high_C": 2.6,
            "RCP60_median_C": 2.2,   "RCP60_low_C": 1.4,  "RCP60_high_C": 3.1,
            "RCP85_median_C": 3.7,   "RCP85_low_C": 2.6,  "RCP85_high_C": 4.8,
            # Baseline IPCC AR5 = 1986-2005 ≈ +0.61°C au-dessus du pré-industriel
            "baseline_above_preindustrial_C": 0.61,
        },
        "bibtex": (
            "@report{ipcc_ar5_2014,\n"
            "  author      = {{IPCC}},\n"
            "  title       = {Climate Change 2014: Synthesis Report},\n"
            "  institution = {IPCC},\n"
            "  address     = {Geneva, Switzerland},\n"
            "  year        = {2014}\n"
            "}"
        ),
    },

    # -------------------------------------------------------------------------
    # DÉCOMPOSITION DU RISQUE
    # -------------------------------------------------------------------------
    "winsemius2016": {
        "key": "winsemius2016",
        "authors": "Winsemius, H.C. et al.",
        "year": 2016,
        "title": "Global drivers of future river flood risk",
        "journal": "Nature Climate Change",
        "volume": 6,
        "pages": "381–385",
        "doi": "10.1038/nclimate2893",
        "key_values": {
            # Décomposition de l'augmentation du risque : CC vs exposition
            # Pour l'Europe, à l'horizon 2030 (RCP 6.0) — Fig. 3
            "share_climate_change_pct": 40.0,   # part du CC dans l'augmentation
            "share_exposure_growth_pct": 60.0,   # part de la croissance de l'exposition
            "note": "Estimation moyenne Europe à court terme; ratio varie avec le scénario",
        },
        "bibtex": (
            "@article{winsemius2016,\n"
            "  author  = {Winsemius, Hessel C. and others},\n"
            "  title   = {Global drivers of future river flood risk},\n"
            "  journal = {Nature Climate Change},\n"
            "  volume  = {6},\n"
            "  pages   = {381--385},\n"
            "  year    = {2016},\n"
            "  doi     = {10.1038/nclimate2893}\n"
            "}"
        ),
    },

    # -------------------------------------------------------------------------
    # DONNÉES BELGES — PERTES HISTORIQUES
    # -------------------------------------------------------------------------
    "assuralia2021": {
        "key": "assuralia2021",
        "authors": "Assuralia",
        "year": 2021,
        "title": "Les inondations de juillet 2021 — Bilan des sinistres",
        "publisher": "Assuralia (Union professionnelle des entreprises d'assurances)",
        "url": "https://www.assuralia.be",
        "key_values": {
            "insured_losses_2021_MEUR": 2500.0,  # pertes assurées confirmées
            "claims_count_approx": 100000,         # nombre de sinistres approximatif
        },
        "bibtex": (
            "@techreport{assuralia2021,\n"
            "  author      = {Assuralia},\n"
            "  title       = {Les inondations de juillet 2021 --- Bilan des sinistres},\n"
            "  institution = {Assuralia},\n"
            "  year        = {2021},\n"
            "  url         = {https://www.assuralia.be}\n"
            "}"
        ),
    },

    "emdat_cred": {
        "key": "emdat_cred",
        "authors": "CRED (Centre for Research on the Epidemiology of Disasters)",
        "year": 2024,
        "title": "EM-DAT: The Emergency Events Database",
        "publisher": "Université catholique de Louvain (UCLouvain)",
        "url": "https://www.emdat.be",
        "key_values": {
            "note": "Base de données principale pour les pertes historiques belges",
        },
        "bibtex": (
            "@misc{emdat_cred,\n"
            "  author       = {{CRED}},\n"
            "  title        = {{EM-DAT}: The Emergency Events Database},\n"
            "  howpublished = {\\url{https://www.emdat.be}},\n"
            "  year         = {2024},\n"
            "  note         = {Universit\\'e catholique de Louvain}\n"
            "}"
        ),
    },

    "swiss_re_sigma": {
        "key": "swiss_re_sigma",
        "authors": "Swiss Re Institute",
        "year": 2023,
        "title": "Sigma — Natural catastrophes and inflation in 2022",
        "publisher": "Swiss Re",
        "url": "https://www.swissre.com/sigma",
        "key_values": {
            # AAL inondations Europe de l'Ouest
            "flood_aal_pct_gdp_min": 0.03,   # % du PIB/an, borne basse
            "flood_aal_pct_gdp_max": 0.05,   # % du PIB/an, borne haute
            # Taux de couverture assurance naturelle (protection gap)
            "insured_share_natcat_pct_min": 35.0,
            "insured_share_natcat_pct_max": 40.0,
        },
        "bibtex": (
            "@techreport{swiss_re_sigma,\n"
            "  author      = {{Swiss Re Institute}},\n"
            "  title       = {Sigma --- Natural catastrophes and inflation in 2022},\n"
            "  institution = {Swiss Re},\n"
            "  year        = {2023},\n"
            "  url         = {https://www.swissre.com/sigma}\n"
            "}"
        ),
    },

    # -------------------------------------------------------------------------
    # RÉGLEMENTATION / SOLVABILITÉ
    # -------------------------------------------------------------------------
    "eiopa2014": {
        "key": "eiopa2014",
        "authors": "EIOPA",
        "year": 2014,
        "title": "Technical Specification for the Preparatory Phase (Part I) — "
                 "Solvency II Standard Formula Natural Catastrophe module",
        "publisher": "European Insurance and Occupational Pensions Authority",
        "url": "https://www.eiopa.europa.eu",
        "key_values": {
            "confidence_level_SCR_pct": 99.5,    # VaR 99.5% sur 1 an
            "note": "Formule standard QIS5 — SCR nat-cat approximation",
        },
        "bibtex": (
            "@techreport{eiopa2014,\n"
            "  author      = {{EIOPA}},\n"
            "  title       = {Technical Specification for the Preparatory Phase},\n"
            "  institution = {EIOPA},\n"
            "  year        = {2014},\n"
            "  url         = {https://www.eiopa.europa.eu}\n"
            "}"
        ),
    },

    "ec_cba_guide2014": {
        "key": "ec_cba_guide2014",
        "authors": "European Commission",
        "year": 2014,
        "title": "Guide to Cost-Benefit Analysis of Investment Projects — "
                 "Economic appraisal tool for Cohesion Policy 2014-2020",
        "publisher": "Publications Office of the EU",
        "doi": "10.2776/97516",
        "key_values": {
            "discount_rate_social_pct": 3.0,   # taux d'actualisation social recommandé
            "discount_rate_alt_pct": 5.0,       # taux alternatif
        },
        "bibtex": (
            "@techreport{ec_cba_guide2014,\n"
            "  author      = {{European Commission}},\n"
            "  title       = {Guide to Cost-Benefit Analysis of Investment Projects},\n"
            "  institution = {Publications Office of the EU},\n"
            "  year        = {2014},\n"
            "  doi         = {10.2776/97516}\n"
            "}"
        ),
    },

    # -------------------------------------------------------------------------
    # MACROÉCONOMIE BELGE
    # -------------------------------------------------------------------------
    "eurostat2022": {
        "key": "eurostat2022",
        "authors": "Eurostat",
        "year": 2022,
        "title": "Regional GDP in Europe — NUTS 2 and NUTS 3 (2022)",
        "publisher": "European Commission",
        "url": "https://ec.europa.eu/eurostat",
        "key_values": {
            "belgium_gdp_BEUR": 550.0,      # PIB Belgique 2022 en Brd€
            "flanders_share_pct": 55.0,      # part du PIB, Région flamande
            "wallonia_share_pct": 25.0,      # part du PIB, Région wallonne
            "brussels_share_pct": 20.0,      # part du PIB, Région bruxelloise
        },
        "bibtex": (
            "@misc{eurostat2022,\n"
            "  author       = {{Eurostat}},\n"
            "  title        = {Regional {GDP} in {Europe} --- {NUTS} 2 and {NUTS} 3 (2022)},\n"
            "  howpublished = {\\url{https://ec.europa.eu/eurostat}},\n"
            "  year         = {2022}\n"
            "}"
        ),
    },

    "assuralia_penetration": {
        "key": "assuralia_penetration",
        "authors": "Assuralia",
        "year": 2022,
        "title": "Statistiques du marché de l'assurance belge 2022",
        "publisher": "Assuralia",
        "url": "https://www.assuralia.be",
        "key_values": {
            "home_insurance_penetration_pct": 95.0,  # taux de pénétration assurance habitation
        },
        "bibtex": (
            "@techreport{assuralia_penetration,\n"
            "  author      = {Assuralia},\n"
            "  title       = {Statistiques du march\\'e de l'assurance belge 2022},\n"
            "  institution = {Assuralia},\n"
            "  year        = {2022},\n"
            "  url         = {https://www.assuralia.be}\n"
            "}"
        ),
    },
}


def get_bibtex_all() -> str:
    """Retourne toutes les références en format BibTeX concaténé."""
    entries = []
    for src in SOURCES.values():
        if "bibtex" in src:
            entries.append(src["bibtex"])
    return "\n\n".join(entries)


def get_source(key: str) -> dict:
    """Retourne une source par sa clé (lève KeyError si absente)."""
    if key not in SOURCES:
        raise KeyError(
            f"Source '{key}' introuvable. Sources disponibles: {list(SOURCES.keys())}"
        )
    return SOURCES[key]
