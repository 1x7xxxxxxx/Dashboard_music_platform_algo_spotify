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
    # ── L'ORDRE DU MENU — réorganisé le 2026-09-22 sur retour d'écran ──────────
    #
    # Neuf demandes, formulées en regardant la barre latérale. Elles se ramènent à
    # une seule règle : **le menu suit le parcours, pas la plomberie.**
    #
    #   1. l'accueil, seul en tête — trois gestes y étaient empilés
    #   2. je configure          → « ⚙️ Configuration », avec son % d'avancement
    #   3. je regarde mes chiffres → « 📊 Analytics plateformes », AVANT le premium
    #   4. je vois ce que j'achète → « 💎 Premium »
    #
    # Ce qui a changé, et pourquoi chaque déplacement plutôt qu'un autre :
    #
    # « 🔮 Prédiction algos Spotify » N'EST PLUS UNE SECTION. Elle n'en portait
    # qu'une, et cette page est PAYANTE : une section d'un seul élément payant
    # posée à côté de « 💎 Premium — ce que l'abonnement ouvre » séparait la
    # promesse du produit de la liste de ce qu'on paie. Elle ouvre donc le premium,
    # à sa place : c'est la page que l'abonnement vend en premier.
    #
    # « 📣 Publicité Meta Ads » N'EST PLUS UNE SECTION non plus. Elle n'en portait
    # qu'une, gratuite, et c'est une plateforme comme les autres — elle rejoint
    # « 📊 Analytics plateformes », juste sous Spotify + S4A, parce que c'est la
    # source qu'on croise le plus souvent avec les écoutes.
    #
    # « 🚀 Mise en route » RETOURNE dans la configuration, juste avant « 🚦 Santé
    # onboarding ». L'assistant et le contrôle de ce qu'il a produit se lisent dans
    # cet ordre-là ; en tête de menu, l'assistant proposait d'installer sans dire
    # ce qui était déjà installé.
    #
    # « ⬇️ Export CSV » RETOURNE sous « 👤 Compte », entre la facturation et le
    # parrainage — sa place d'avant le 2026-09-22. Une sortie brute de ses propres
    # données est un geste de compte, pas un geste d'analyse.
    #
    # « 📄 Export PDF » devient « 📄 Rapport de carrière PDF » et PASSE EN DERNIER
    # d'« Analytics plateformes ». Le nom d'abord : « Export PDF » décrit un format,
    # « Rapport de carrière » décrit ce qu'on obtient — et c'est ce qu'on cherche.
    # La place ensuite : il vient après les plateformes parce qu'il les RÉSUME ;
    # en troisième entrée du menu, il proposait un résumé avant qu'il y ait quoi
    # que ce soit à résumer.
    #
    # « 🎯 Faire piloter mes campagnes » suit immédiatement le rapport. L'ordre
    # raconte quelque chose : voilà ta carrière en un document, et voilà qui peut
    # s'en occuper. Elle quitte donc « 👤 Compte », où elle était rangée par
    # facturation plutôt que par usage.
    ("start",     "",
     [("🏠 Accueil", "home")]),
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
      # ⚠️ HYPEDDIT EST UNE SAISIE, PAS UNE PLATEFORME (2026-09-21). Elle vivait
      # dans « 📊 Analytics plateformes », entre Instagram et Data Wrapped —
      # vrai côté machine, faux côté parcours : les visites et clics d'un smart
      # link se recopient à la main depuis son tableau de bord. Même déplacement,
      # même raison, que « 📝 Saisie S4A » le 2026-09-12.
      ("📱 Hypeddit (saisie smart link)", "hypeddit"),
      ("🗄️ Santé des données", "db_health")]),
    # ── CE QU'ON REGARDE, AVANT CE QU'ON ACHÈTE — 2026-09-22 ──────────────────
    #
    # Cette section était SOUS « 💎 Premium ». Un artiste gratuit voyait donc six
    # cadenas avant d'atteindre ses propres chiffres, ce qui inverse l'ordre des
    # choses : on regarde d'abord ce qu'on a, on décide ensuite si on paie pour
    # plus.
    ("analytics", "📊 Analytics plateformes",
     [("🎵 Spotify + Spotify for Artists", "spotify_s4a_combined"),
      ("📣 Publicité Meta Ads", "meta_ads_overview"),
      ("🎎 Apple Music", "apple_music"),
      ("🎬 YouTube", "youtube"),
      ("☁️ SoundCloud", "soundcloud"),
      ("📸 Instagram", "instagram"),
      # ⚠️ « 🎁 Data Wrapped » a quitté le menu le 2026-09-21, et sa ROUTE survit.
      # Son contenu est rendu par « 🎵 Spotify + Spotify for Artists », replié : ce
      # qu'on y saisit sont les chiffres du Spotify Wrapped FOR ARTISTS, donc des
      # chiffres Spotify. Une entrée par SOURCE DE SAISIE éparpillait une seule
      # histoire. La route reste valide — des liens la visent.
      ("🎯 Faire piloter mes campagnes", "service")]),
    # ── CE QUI SE VEND, RASSEMBLÉ — 2026-09-21, complété le 2026-09-22 ─────────
    #
    # Les six pages Premium étaient dispersées dans CINQ sections, chacune au
    # milieu de pages gratuites : six 🔒 semés dans le menu, sans qu'aucun écran ne
    # dise ce que l'abonnement contient — et pour un abonné, aucune façon de voir
    # ce qu'il paie. Depuis le 2026-09-22 l'en-tête porte lui aussi un cadenas
    # (`nav_badges.section_badge`) : 🔒 rouge quand rien n'est ouvert, 🔓 vert quand
    # tout l'est.
    #
    # ⚠️ `meta_ads_overview` N'EST PAS ICI : elle est GRATUITE. Rassembler « ce qui
    # se vend » ne veut pas dire rassembler « tout ce qui touche à Meta » — le
    # critère est le PLAN, et il se lit dans `stripe_schema.PLAN_FEATURES`, pas dans
    # le thème de la page. Un garde le vérifie
    # (`tests/test_the_campaign_view_plots_what_it_promises.py`) : cette liste et le
    # catalogue de prix ne peuvent plus diverger en silence.
    ("premium",   "💎 Premium — ce que l'abonnement ouvre",
     # ⚠️ LE RAPPORT OUVRE LA SECTION — déplacé le 2026-09-22 au soir, quelques heures
     # après l'avoir mis en dernier d'« Analytics ». Les deux placements se défendent, et
     # celui-ci gagne pour une raison que l'autre n'avait pas : le rapport est ce que
     # l'abonnement donne de plus TANGIBLE — un document qu'on emporte. En tête de la
     # liste de ce qu'on paie, il répond à « qu'est-ce que j'achète » avant les cinq
     # pages d'analyse, qu'il faut ouvrir pour comprendre.
     #
     # Ce qu'on perd, et il faut le dire : en dernier d'« Analytics », l'ordre racontait
     # « voilà tes plateformes, voilà leur résumé ». Ici le résumé est loin de ce qu'il
     # résume. C'est un arbitrage entre deux récits, pas une correction.
     [("📄 Rapport de carrière PDF", "export_pdf"),
      ("🚀 Prédiction déclenchement algos Spotify (DW, Radio, RR…)", "trigger_algo"),
      ("🔀 Impact de mes campagnes (toutes plateformes)", "meta_x_spotify"),
      ("🎨 Visuels de campagne", "meta_creatives"),
      ("🌍 Qui a vu tes pubs (pays, âge, placement)", "meta_breakdowns"),
      ("📊 CPR Optimizer", "meta_cpr_optimizer"),
      ("📈 Prévisions revenus", "revenue_forecast")]),
    ("revenue",   "💶 Revenus",
     [("💰 Distributeurs (iMusician, DistroKid…)", "imusician"),
      ("🎼 SACEM", "sacem")]),
    ("account",   "👤 Compte",
     [("👤 Mon compte", "account"),
      ("💳 Billing", "billing"),
      ("⬇️ Export CSV", "export_csv"),
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
