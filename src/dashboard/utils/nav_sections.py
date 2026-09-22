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
    # ── LA TÊTE DU MENU — 2026-09-22 ────────────────────────────────────────
    #
    # Demandé en regardant l'écran : « accueil et ensuite guide de démarrage »,
    # puis les deux exports. Trois gestes dans l'ordre où on les fait quand on
    # arrive : je regarde où j'en suis, je branche ce qui manque, j'emporte le
    # résultat.
    #
    # Les exports étaient dispersés — « 📄 Export PDF » au milieu des six pages
    # Premium, « ⬇️ Export CSV » sous « Compte », entre la facturation et le
    # parrainage. Aucun des deux ne se trouvait en cherchant « je veux mon
    # rapport » : le premier demandait de connaître son plan, le second de penser
    # à son compte. Ils sont maintenant là où on les cherche.
    #
    # ⚠️ « 📄 Export PDF » est PREMIUM (décision du 2026-09-04 : « la sortie brute
    # reste gratuite, la mise en forme est le service »). Le remonter met donc un
    # 🔒 rouge en troisième entrée pour un compte gratuit. C'est assumé : l'entrée
    # reste visible pour dire ce que l'abonnement contient, et depuis le
    # 2026-09-22 le cadenas le dit en couleur.
    ("start",     "",
     [("🏠 Accueil", "home"),
      ("🚀 Mise en route (assistant)", "onboarding"),
      ("📄 Export PDF", "export_pdf"),
      ("⬇️ Export CSV", "export_csv")]),
    ("data",      "⚙️ Configuration de streaMLytics",
     [("🚦 Santé onboarding", "onboarding_health"),
      ("🔑 Credentials API + imports CSV", "credentials"),
      # « 📋 État de tes plateformes » a été RETIRÉE du menu le 2026-09-05 : chaque
      # onglet de Credentials porte désormais les quatre mêmes pastilles pour SA
      # plateforme, calculées par les mêmes fonctions. Une page entière pour redire
      # ce que l'onglet montre là où l'on agit est une redirection de plus, pas une
      # information de plus. La ROUTE survit (voir `_main_body`) — des liens la visent.
      ("🔗 Mapping cross-plateforme", "meta_mapping"),
      ("📝 Saisie S4A (playlist & Discovery)", "saisie_s4a"),
      # ⚠️ HYPEDDIT REJOINT LA CONFIGURATION le 2026-09-21, juste après Saisie S4A.
      #
      # Elle vivait dans « 📊 Analytics plateformes », entre Instagram et Data
      # Wrapped. C'était vrai côté machine et faux côté parcours : Hypeddit
      # n'est pas une plateforme qu'on COLLECTE, c'est un formulaire qu'on
      # REMPLIT — les visites et clics d'un smart link se recopient à la main
      # depuis leur tableau de bord. Elle appartient donc au même geste que la
      # saisie S4A, et se fait au même moment.
      #
      # C'est le même déplacement, pour la même raison, que « 📝 Saisie S4A »
      # elle-même le 2026-09-12 : elle était rangée avec le modèle qu'elle
      # nourrit, alors que c'est une SAISIE.
      ("📱 Hypeddit (saisie smart link)", "hypeddit"),
      ("🗄️ Santé des données", "db_health")]),
    ("advanced",  "🔮 Prédiction algos Spotify",
     [("🚀 Prédiction déclenchement algos Spotify (DW, Radio, RR…)", "trigger_algo")]),
    # ── CE QUI SE VEND, RASSEMBLÉ — 2026-09-21 ────────────────────────────────
    #
    # Les six pages Premium étaient dispersées dans CINQ sections, chacune au
    # milieu de pages gratuites. Conséquence pour un artiste Free : six 🔒 semés
    # dans le menu, sans qu'aucun écran ne dise ce que l'abonnement contient — et
    # pour un artiste Premium, aucune façon de voir ce qu'il paie.
    #
    # Elles vivent maintenant ensemble, juste sous la prédiction, qui est la
    # promesse du produit (déplacement du 2026-09-12, même raison).
    #
    # ⚠️ `meta_ads_overview` N'EST PAS ICI : elle est gratuite. Rassembler « ce
    # qui se vend » ne veut pas dire rassembler « tout ce qui touche à Meta » —
    # le critère est le PLAN, et il se lit dans `stripe_schema.PLAN_FEATURES`,
    # pas dans le thème de la page. Un garde le vérifie
    # (`tests/test_the_campaign_view_plots_what_it_promises.py`) : cette
    # liste et le catalogue de prix ne peuvent plus diverger en silence.
    ("premium",   "💎 Premium — ce que l'abonnement ouvre",
     [("🔀 Impact de mes campagnes (toutes plateformes)", "meta_x_spotify"),
      ("🎨 Visuels de campagne", "meta_creatives"),
      ("🌍 Qui a vu tes pubs (pays, âge, placement)", "meta_breakdowns"),
      ("📊 CPR Optimizer", "meta_cpr_optimizer"),
      ("📈 Prévisions revenus", "revenue_forecast")]),
    ("analytics", "📊 Analytics plateformes",
     [("🎵 Spotify + Spotify for Artists", "spotify_s4a_combined"),
      ("🎎 Apple Music", "apple_music"),
      ("🎬 YouTube", "youtube"),
      ("☁️ SoundCloud", "soundcloud"),
      ("📸 Instagram", "instagram")]),
    # ⚠️ « 🎁 Data Wrapped » a quitté le menu le 2026-09-21, et sa ROUTE survit.
    #
    # Son contenu est rendu par « 🎵 Spotify + Spotify for Artists », replié : ce
    # qu'on y saisit sont les chiffres du Spotify Wrapped FOR ARTISTS — listeners,
    # streams, saves, playlist adds — c'est-à-dire des chiffres Spotify. Une
    # entrée de menu par SOURCE DE SAISIE éparpillait une seule histoire.
    #
    # La route reste valide (`data_wrapped.show()` existe toujours) pour la même
    # raison que `process_guide` : des liens la visent, et un artiste qui suit un
    # ancien lien ne doit pas tomber sur un mur.
    ("ads",       "📣 Publicité Meta Ads",
     [("📱 Vue d'ensemble", "meta_ads_overview")]),
    ("revenue",   "💶 Revenus",
     [("💰 Distributeurs (iMusician, DistroKid…)", "imusician"),
      ("🎼 SACEM", "sacem")]),
    ("account",   "👤 Compte",
     [("👤 Mon compte", "account"),
      ("💳 Billing", "billing"),
      # La prestation vit sous la facturation et non dans « 💎 Premium » : ce
      # n'est PAS ce que l'abonnement ouvre, c'est ce qu'un humain fait à côté.
      ("🎯 Faire piloter mes campagnes", "service"),
      ("🎁 Parrainage", "referral")]),
    # ⚡ « Perf. Dashboard » (`perf_monitor`) a ete RETIRE le 2026-09-16, R115 etape 6.
    # Grafana le couvre entierement, et mieux : la vue ne montrait que la session de
    # l'admin qui la regardait, et seulement la phase `view`. Correspondance ligne a
    # ligne verifiee AVANT la suppression : `.claude/dev-docs/grafana-correspondence.md`.
    # Un seul chiffre est abandonne, le « DB ping », avec son declencheur de reouverture.
    ("admin",     "🛠️ Admin / Ops",
     [("📈 Usage Analytics", "usage_analytics"),
      ("🏗️ Monitoring ETL", "airflow_kpi"),
      ("🗂️ Historique ETL", "etl_logs"),
      ("🤖 Perf. Modèles ML", "ml_performance"),
      ("🚨 Alertes", "alerts"),
      ("📊 Referral KPIs", "referral_kpi"),
      ("🎟️ Promo Codes", "promo_admin"),
      ("🔧 Liens & Outils", "useful_links"),
      ("⚙️ Admin", "admin")]),
]
