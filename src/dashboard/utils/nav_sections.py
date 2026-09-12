"""L'ordre du menu — une DÉCLARATION, pas du routage.

Type: Sub
Uses: rien
Depends on: rien
Persists in: nothing

Pourquoi ce module existe
-------------------------
La constante vivait dans `app.py`, qui était **exactement à son plafond de longueur**
(1 073 lignes, cliquet `tests/test_a_file_only_gets_shorter.py`). Toute ligne ajoutée
au menu — y compris le commentaire qui explique un choix, et ce dépôt en exige un —
faisait rougir la CI. Le cliquet a fait son travail : il a refusé la dette et rendu
l'extraction obligatoire, au lieu d'être relevé.

C'est le même geste que `csv_platforms.py` et `platform_sharing.py` le 2026-09-12 : une
déclaration descend hors du module qui la consomme. `app.py` garde le ROUTAGE — la
chaîne `elif page == …` — qui ne dépend pas de cet ordre.

⚠️ Le cliquet avait explicitement DIFFÉRÉ ce découpage : « un découpage de la
navigation ne peut être validé qu'au navigateur », parce que deux causes racines de
navigation ont traversé 3 755 tests verts — le harnais de rendu appelle chaque `show()`
isolément et jamais `_main_body`. L'extraction du 2026-09-12 a donc été vérifiée au
navigateur avant d'être livrée, et cette phrase-là reste vraie pour la prochaine.

La forme
--------
`(identifiant stable, en-tête affiché, [(libellé, clé de page), …])`.

L'identifiant est **stable** et sert de clé de widget (`_nav_<id>`) et de clé i18n
(`nav.section.<id>`) : le renommer casse la sélection en cours des utilisateurs. Un
en-tête vide ne dessine aucun séparateur — c'est ce qui met une entrée en tête de menu
sans lui inventer une catégorie.
"""
from __future__ import annotations

# L'ORDRE EST LE PARCOURS, et il a été révisé trois fois par des parcours réels.
#
# 2026-09-06 : « mets l'onglet santé onboarding juste après mise en route, il faut que
# credential API + CSV soit juste avant mapping cross-plateforme ». Le matin même,
# « Santé onboarding » avait été placée APRÈS Credentials au motif qu'on configure puis
# qu'on vérifie. Le parcours a tranché autrement, et c'est lui qui décide : on ouvre
# l'assistant, on veut savoir ce qui manque, on va le saisir, puis on confirme les
# titres.
#
# 2026-09-12 : quatre déplacements de plus, tous demandés en regardant l'écran.
#   · « 📝 Saisie S4A » REJOINT la configuration, juste après le mapping. Elle était
#     dans « Prédiction algos Spotify » avec le modèle qu'elle nourrit, ce qui est
#     vrai côté machine et faux côté parcours : c'est une SAISIE, au même titre que
#     les credentials et les imports, et elle se fait une fois au début.
#   · La section « 🔮 Prédiction algos Spotify » remonte juste après la configuration.
#     Ce qu'un artiste vient chercher ici est la prédiction ; l'enterrer sous cinq
#     sections d'analytics en faisait une option avancée alors que c'est la promesse.
#   · « 📄 Export PDF » monte sous l'accueil, SANS section. Un rapport n'est pas une
#     catégorie, c'est un geste — et il n'y en avait que deux sous « Rapports &
#     exports », dont l'autre part ailleurs.
#   · « ⬇️ Export CSV » rejoint « Compte » au-dessus du parrainage : emporter ses
#     données est un droit du compte (RGPD), pas une fonctionnalité d'analyse.
# La section « 🎁 Rapports & exports », vidée par ces deux derniers, est supprimée.
#
# ⚠️ `export_pdf` est PREMIUM depuis le 2026-09-04 (décision de prix écrite dans
# `stripe_schema.py` : « la sortie brute reste gratuite, la mise en forme est le
# service »). Le remonter sous l'accueil met donc un 🔒 en deuxième entrée pour un
# artiste Free — conséquence assumée le 2026-09-12, l'entrée restant visible pour
# dire ce que l'offre contient.
NAV_SECTIONS: list = [
    ("start",     "",                       [("🏠 Accueil", "home"),
                                             ("📄 Export PDF", "export_pdf")]),
    ("data",      "⚙️ Configuration de streaMLytics",
     [("🚀 Mise en route (assistant)", "onboarding"),
      ("🚦 Santé onboarding", "onboarding_health"),
      ("🔑 Credentials API + imports CSV", "credentials"),
      # « 📋 État de tes plateformes » a été RETIRÉE du menu le 2026-09-05 : chaque
      # onglet de Credentials porte désormais les quatre mêmes pastilles pour SA
      # plateforme, calculées par les mêmes fonctions. Une page entière pour redire
      # ce que l'onglet montre là où l'on agit est une redirection de plus, pas une
      # information de plus. La ROUTE survit (voir `_main_body`) — des liens la visent.
      ("🔗 Mapping cross-plateforme", "meta_mapping"),
      ("📝 Saisie S4A (playlist & Discovery)", "saisie_s4a"),
      ("🗄️ Santé des données", "db_health")]),
    ("advanced",  "🔮 Prédiction algos Spotify",
     [("🚀 Prédiction déclenchement algos Spotify (DW, Radio, RR…)", "trigger_algo")]),
    ("analytics", "📊 Analytics plateformes",
     [("🎵 Spotify + Spotify for Artists", "spotify_s4a_combined"),
      ("🎵 META x Spotify", "meta_x_spotify"),
      ("🎎 Apple Music", "apple_music"),
      ("🎬 YouTube", "youtube"),
      ("☁️ SoundCloud", "soundcloud"),
      ("📸 Instagram", "instagram"),
      ("📱 Hypeddit", "hypeddit"),
      # Data Wrapped vivait dans « Rapports & exports », à côté des exports PDF/CSV.
      # Ce n'est pas un export : c'est une lecture de ses chiffres, comme les six
      # entrées au-dessus. Déplacé le 2026-09-04 à la demande de l'artiste.
      ("🎁 Data Wrapped", "data_wrapped")]),
    ("ads",       "📣 Publicité Meta Ads",
     [("📱 Vue d'ensemble", "meta_ads_overview"),
      ("🎨 Visuels de campagne", "meta_creatives"),
      ("🌍 Qui a vu tes pubs (pays, âge, placement)", "meta_breakdowns"),
      ("📊 CPR Optimizer", "meta_cpr_optimizer")]),
    ("revenue",   "💶 Revenus",
     [("💰 Distributeurs (iMusician, DistroKid…)", "imusician"),
      ("🎼 SACEM", "sacem"),
      ("📈 Prévisions revenus", "revenue_forecast")]),
    ("account",   "👤 Compte",
     [("👤 Mon compte", "account"),
      ("💳 Billing", "billing"),
      ("⬇️ Export CSV", "export_csv"),
      ("🎁 Parrainage", "referral")]),
    ("admin",     "🛠️ Admin / Ops",
     [("⚡ Perf. Dashboard", "perf_monitor"),
      ("📈 Usage Analytics", "usage_analytics"),
      ("🏗️ Monitoring ETL", "airflow_kpi"),
      ("🗂️ Historique ETL", "etl_logs"),
      ("🤖 Perf. Modèles ML", "ml_performance"),
      ("🚨 Alertes", "alerts"),
      ("📊 Referral KPIs", "referral_kpi"),
      ("🎟️ Promo Codes", "promo_admin"),
      ("🔧 Liens & Outils", "useful_links"),
      ("⚙️ Admin", "admin")]),
]
