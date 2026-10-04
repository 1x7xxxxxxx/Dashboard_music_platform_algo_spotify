# Master Roadmap Checklist — actif

**Roadmap en deux fichiers.** Celui-ci ne porte que ce qui est **ouvert** ; ce qui est livré
ou clos vit dans `.claude/dev-docs/roadmap/archive.md`. Un item passe de l'un à l'autre par
**déplacement** — jamais par duplication ni par effacement.

| Fichier | Contient | Écrit par |
|---|---|---|
| `checklist.md` (ici) | index des tâches ouvertes, reprise, tâches parquées, consignes | l'inscription d'une tâche (R196), `make roadmap-close` |
| `archive.md` | tâches livrées ou closes, récits, historique de l'actif | `make roadmap-close` (R199), `roadmap-keeper` pour un lot |

**Le cycle d'une action (R196 · R198 · R199)** : (1) une ligne `| Rnnn | … <!-- critic: requis|non — raison --> | P | mesure |`
dans l'index, commitée seule ; (2) le code, commité avec « Rnnn : … » — refusé sinon, avant
l'édition et au commit ; (3) `make roadmap-close ID=Rnnn NOTE="…"`. La discipline est MESURÉE :
`make roadmap-discipline` (R197), chaque nuit et dans le récap du matin.

Ce fichier reste court (R200, 2026-09-26) : la prose d'historique qui l'avait porté à 499
lignes vit dans l'archive, sous « 🗄️ Historique de l'actif ». Plafond gardé par
`tests/test_the_resume_header_is_checked.py`.

Resume after `/clear`: *"Read `.claude/dev-docs/roadmap/checklist.md` and continue with the next open row."*

---


## 📋 Tâches ouvertes (index — détail plus bas)

Index des tâches **qu'on peut commencer maintenant** — chaque ligne décide de son
code-critic. À la livraison : `make roadmap-close ID=Rnnn` (écrit l'archive, retire la ligne).

| id | Tâche | P | Mesuré par |
|---|---|---|---|
| R367 | Harnais — les 4 trous (ORCH-01, ORCH-03, RUN-04, RUN-06) renvoient vers R284, qui vit dans `product-backlog.md` derrière un déclencheur de charge : écrire leurs SONDES maintenant (elles rendent l'état mesuré, pas un échec), garder le code de scalabilité derrière le déclencheur <!-- critic: requis — une sonde qui ne doit pas rougir sur un écart accepté --> **Critic 2026-10-05 : BUILD-MODIFIED** — ORCH-01 (boucles par locataire lues en AST dans `airflow/dags/*_daily.py` contre un ensemble accepté) et RUN-06 (`enable_pool(maxconn=8)` ≥ concurrence déclarée, lu en AST) en `pytest:`, pas en `cmd:` (sinon jamais « active ») ; RUN-04 reste `absent` (sans navigateur, aucune mesure honnête) ; ORCH-03 DO-NOT-BUILD (aucun compteur à mesurer) ; chaque sonde rougit si son prédicat ne voit aucun site. <!-- scope: tests/, tools/dev/, .claude/dev-docs/architecture/, Makefile --> | P3 | `make harness-report` : trous 4 → 2 (ORCH-01, RUN-06 mesurés ; RUN-04, ORCH-03 restent des trous déclarés) |
| R370 | Restes de R369 et sites frères de `check-then-insert-loses-the-race` (balayage 2026-10-05) : (a) compteur d'échecs de connexion lu puis réécrit (`src/dashboard/auth.py:~296`, `src/api/auth.py:~115`) → seuil de verrouillage sous-compté en parallèle ; (b) `find_identity_conflict` (`credentials/_core.py:519`) contrôle inter-locataires sans contrainte unique → deux locataires peuvent revendiquer le même profil ; (c) `update_platform_secret` (`credential_loader.py:155`) réécrit le blob chiffré sans verrou → une clé concurrente perdue (rafraîchissement Meta vs collecte Instagram) ; (d) `customer.subscription.deleted` / `invoice.payment_failed` encore clés par client, pas par abonnement ; (e) `STALE_AFTER_HOURS=1` non calibré ; (f) plancher `stripe>=8.0.0` à épingler ; (g) TRANCHÉ 2026-10-05 : le mois offert déjà posé chez le parrain RESTE acquis si le filleul est remboursé ; on journalise le remboursement (`charge.refunded`) sans retirer le coupon <!-- critic: requis — (b) touche l'isolation des locataires --> **Critic 2026-10-05 : BUILD-MODIFIED** — (a) incrément ET verrou dans UNE requête (`CASE WHEN … >= 5`), un helper sous `src/utils/` ; (b) pas d'index unique : verrou consultatif + contrôle + écriture dans UNE transaction explicite (le handler est autocommit), dans `write_platform_identity`, clés normalisées triées, test à barrière vu rouge ; (c) `autocommit=False` + `lock_timeout`, et un déchiffrement raté ABANDONNE au lieu d'écraser les autres clés (perte de données dans les lignes touchées) ; (d) `payment_failed` : l'id d'abonnement se lit dans la facture (lire un vrai payload 15.x), repli client seulement si l'id stocké est NULL ; (e) DO-NOT-BUILD — aucune donnée, garder 1 h ; (f) `stripe>=15.6.1,<16`, relock, `requirements.txt` ; (g) tranché : conservé, journalisé. <!-- scope: src/dashboard/auth.py, src/api/auth.py, src/dashboard/views/credentials/, src/utils/tenant_identity.py, src/utils/credential_loader.py, src/api/routers/stripe_webhook.py, src/utils/stripe_unmatched.py, migrations/, pyproject.toml, requirements.txt, uv.lock, tests/, .claude/dev-docs/, .test_durations --> | P2 | un test de concurrence par site (a-c) rouge sur le code d'avant, vert après |
| R371 | Accueil — mise en forme (notes V1-V4 du 2026-10-05) : total des écoutes en plus grand ; camembert des parts par plateforme (Spotify, YouTube, Apple, SoundCloud) avec valeurs, lu par `v_platform_totals` (la porte des totaux — jamais un cumul sommé) ; tuiles Meta Ads + Hypeddit sur une ligne, Shazam + Instagram sur une autre ; légende « prédites maximum atteintes » → « maximales » (aucune faute trouvée sur les noms DW / Radio / RR dans le code — vérifier au rendu) <!-- critic: non — mise en page, lecteur existant --> <!-- scope: src/dashboard/views/home.py, src/dashboard/views/home_tiles.py, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest de l'accueil : un `go.Pie` à 4 parts dont la somme = total affiché ; l'ordre des tuiles est Meta·Hypeddit puis Shazam·Instagram |
| R372 | Accueil — bloc « Dernière sortie » sans filtre (V5) : nommer la sortie et dire que c'est la dernière ; % par playlist (existe, `home_tiles.py:457`) + BUDGET Meta nécessaire = écart au seuil × coût par écoute au meilleur CPR — la même fonction que la vue algo (R381), pas une seconde formule <!-- critic: requis — un montant en euros sur lequel l'artiste agit --> <!-- scope: src/dashboard/views/home.py, src/dashboard/views/home_tiles.py, src/dashboard/views/trigger_algo/, src/dashboard/utils/, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | un test : le budget de l'accueil et celui de la vue algo sortent du même appel pour le même titre ; titre = dernière sortie de `v_s4a_song_measured_span` |
| R373 | Accueil — retirer « Ce que ta publicité a appris », le bouton PDF, « Statut des pipelines » et « Ce qui alimente tes chiffres » (V6) ; chaque bloc va où il n'est pas déjà : conseil Meta → vue croisée (R378) ; fraîcheur → déjà dans Santé onboarding / Alertes ; pipelines → Monitoring ETL (admin) ; PDF → entrée de menu sous l'accueil (R386). Le `</div>` (V7) est déjà corrigé par 0d90552d, pas encore en prod <!-- critic: non — retrait, chaque contenu a déjà une autre maison vérifiée --> <!-- scope: src/dashboard/views/home.py, src/dashboard/views/home_meta_advice.py, src/dashboard/views/onboarding_health.py, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest de l'accueil : aucun des quatre titres rendu ; un test par bloc déplacé qui le trouve dans sa page d'arrivée |
| R374 | Mise en route — « 1 streaMLytics en bref » (V11, V12, V55) : un graphique GÉNÉRIQUE, étiqueté « exemple », jamais tiré des données de l'artiste (R347 avait retiré celui qui l'était), puis les deux promesses (prédiction algo, optimisation campagne) en deux graphiques de même taille, dans l'ordre ; un seul module de figures d'exemple, réutilisé par l'aperçu algo (DW / RR / Radio n'y a aucun graphique) <!-- critic: non — figures d'exemple étiquetées, aucune donnée lue --> <!-- scope: src/dashboard/views/onboarding.py, src/dashboard/views/algo_preview.py, src/dashboard/utils/, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest mise en route sur un locataire VIDE : 3 figures rendues, toutes portant « exemple » ; l'aperçu algo rend la même figure |
| R375 | Mapping cross-plateforme (V16) : les deux parcours « Titres et couverture » puis « Campagnes Meta » en deux grands titres, chacun dans son expander, l'un sous l'autre (aujourd'hui deux onglets) <!-- critic: non — mise en page --> <!-- scope: src/dashboard/views/meta_mapping/, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest : deux expanders dans cet ordre, plus de `st.tabs` sur la page |
| R376 | Saisie S4A — une seule sous-vue (V17-V21) : « Signaux du mois » gardé, « Titres couverts par la saisie » à sa fin ; « Résultats réalisés » et « Le pari du modèle, et ce qui est arrivé » → vue algo unique (R380) ; « Fraîcheur des saisies » → page admin <!-- critic: non — déplacements, les fonctions de `s4a_entry_insight` ne changent pas --> <!-- scope: src/dashboard/views/saisie_s4a.py, src/dashboard/utils/s4a_entry_insight.py, src/dashboard/views/trigger_algo/, src/dashboard/views/admin.py, src/dashboard/views/admin/, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest : saisie_s4a n'a plus de `st.tabs` ; chaque section déplacée trouvée dans sa page d'arrivée |
| R377 | Hypeddit (V22-V25) : saisie gardée ; expander « Récupérer tes chiffres sur Hypeddit » — étapes d'action seulement ; statistiques avec un filtre CAMPAGNE (défaut : les deux dernières sorties) qui compare visites, clics et dépense Meta ; historique replié par défaut <!-- critic: non — filtre et mise en page --> <!-- scope: src/dashboard/views/hypeddit.py, src/dashboard/utils/, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest : filtre campagne présent, deux sorties par défaut ; l'historique est dans un expander fermé |
| R378 | Vue croisée « Meta × Hypeddit × Spotify × Insta × Shazam » (V8, V29, V30, V35, V36, V70) : UNE page en tête d'Analytics, texte + graphique, qui fusionne Publicité Meta Ads (onglet « Tout mon funnel » compris), Visuels de campagne, Qui a vu tes pubs, Instagram — et rapatrie « quelle tranche d'âge clique le moins cher » du CPR Optimizer ; un seul jeu de filtres (compte, campagne, période) lu par toutes les sections ; l'entonnoir Insta → Hypeddit → Spotify, Insta Ads, impact Insta et Shazam ; Spotify+S4A, Apple, YouTube, SoundCloud restent séparées ; anciennes routes gardées en alias. **Confirmé par le propriétaire le 2026-10-05**, contenu de « Tout mon funnel » repris tel quel. Prémisse corrigée : aucune vue croisée n'a été supprimée (git log), c'est le contenu de `meta_x_spotify` <!-- critic: requis — refonte de 5 pages et des filtres (ADR) --> <!-- scope: src/dashboard/views/meta_ads_overview.py, src/dashboard/views/meta_x_spotify.py, src/dashboard/views/meta_creatives.py, src/dashboard/views/meta_breakdowns.py, src/dashboard/views/instagram.py, src/dashboard/views/meta_cpr_optimizer.py, src/dashboard/views/home_meta_advice.py, src/dashboard/utils/, src/dashboard/routes.py, src/dashboard/app.py, docs/adr/, .claude/dev-docs/, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | menu Analytics = Spotify+S4A, Vue croisée, Apple, YouTube, SoundCloud ; `test_every_route_resolves` vert sur les 4 alias ; un test : chaque section lit LE filtre de la page, aucune n'en déclare un second |
| R379 | Retirer la page « 📌 Récap » (V26) : elle ne dessine rien, elle liste dix liens ; route gardée en alias vers l'accueil (des liens la visent) <!-- critic: non — retrait d'une entrée de menu --> <!-- scope: src/dashboard/utils/nav_sections.py, src/dashboard/routes.py, src/dashboard/views/recap.py, src/dashboard/content/, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | `test_every_route_resolves` vert ; « recap » absent de `NAV_SECTIONS` |
| R380 | Vue algo UNIQUE — structure (V18, V20, V57-V63, V65, V67-V69, V73, V74) : les 4 onglets de « Prédiction déclenchement » fusionnés en une page lue de haut en bas, avec séparateurs ; elle absorbe Paramètres de mes campagnes, Prévisions revenus (+ « où j'en suis vs somme des dépenses »), « Résultats réalisés » et « Le pari du modèle » de la saisie S4A ; jauges 0-100 gardées, noms de playlist en pastilles ; retirer « prochain geste titre par titre » et « vrai pour tout ton catalogue » ; « valeurs qui déclencheraient » : 2 titres, en graphiques ; Budget & ROI en graphiques ; ordre DW → Radio → RR PARTOUT (aujourd'hui DW·RR·Radio ici, RR·DW·Radio au budget) ; « Comment lire » réécrit (il décrit 7 onglets qui n'existent plus — défaut trouvé). Section Premium = Aperçu + cette vue <!-- critic: requis — fusion de 4 pages Premium, ce que l'abonnement vend --> <!-- scope: src/dashboard/views/trigger_algo/, src/dashboard/views/meta_campaign_settings.py, src/dashboard/views/revenue_forecast.py, src/dashboard/views/saisie_s4a.py, src/dashboard/views/algo_preview.py, src/dashboard/utils/, src/dashboard/routes.py, src/dashboard/app.py, src/database/stripe_schema.py, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | section Premium = 2 entrées ; AppTest : aucun `st.dataframe` hors expander de détail ; une constante d'ordre DW/Radio/RR lue par toutes les figures |
| R381 | Vue algo — le contenu qui décide (V56, V64, V66, V71, V72) : SHAP par playlist en ordre décroissant, valeur atteinte vs valeur nécessaire, avec les seuils Spotify (deux jeux divergent : 130/137/639 dans le guide, 417/1333/8423 au budget — même grandeur ou deux notions, à lire dans le code) ; coût Meta pour combler l'écart au meilleur CPR et au CPR moyen ; recommandations détaillées du CPR Optimizer pour la dernière sortie ; réglages recommandés tirés des campagnes au meilleur CPR (âge, placement…) avec ce qui change ; aperçu gratuit : un SHAP des valeurs manquantes <!-- critic: requis — des recommandations et des montants que l'artiste applique --> <!-- scope: src/dashboard/views/trigger_algo/, src/dashboard/views/algo_preview.py, src/dashboard/views/meta_cpr_optimizer.py, src/dashboard/views/meta_campaign_settings.py, src/dashboard/utils/, src/ml/, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | un test : seuils lus d'UNE constante ; le coût pour combler sort de la fonction partagée avec l'accueil (R372) ; recommandations calculées sur un jeu de campagnes fixé, rouges si le meilleur CPR change |
| R382 | Spotify + S4A (V27, V28, V31-V34) : dépense Meta en courbe CUMULÉE sur son propre axe (au lieu de €/jour) ; sélecteur « titres » limité à ceux qui bougent ; légende de l'indice de popularité sur le graphique ; axe secondaire de popularité borné au max observé arrondi (0-20 ici, 60 ailleurs), au lieu de 0-100 fixe ; « sorties à J égal » et Wrapped inchangés <!-- critic: non — figures existantes --> <!-- scope: src/dashboard/views/spotify_s4a_combined.py, src/dashboard/utils/, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | test pur : la borne d'axe suit le max des données ; AppTest : la trace Meta est cumulative (monotone) |
| R383 | Apple Music (V37) : l'expander « Shazams par chanson » devient un graphique, sur la même ligne, à droite du top 10 des écoutes cumulées <!-- critic: non — mise en page --> <!-- scope: src/dashboard/views/apple_music.py, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest : deux figures dans un `st.columns(2)`, plus d'expander Shazam |
| R384 | YouTube (V38-V41) : « Évolution de la chaîne » gardée, textes explicatifs retirés ; la bulle vues × likes devient un classement par ratio like/vue ; 2-3 figures de plus sur les données déjà collectées (vues gagnées par vidéo entre relevés, commentaires par vue, âge vs vues). Les abonnés gagnés PAR VIDÉO ne sont pas collectés : Data API v3 seulement — l'inventaire de l'Analytics API est R394 <!-- critic: non — figures sur données existantes --> <!-- scope: src/dashboard/views/youtube.py, src/dashboard/utils/, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest : classement trié par ratio ; aucune figure ne somme un cumul (`cumulative-counter-drawn-as-its-own-history`) |
| R385 | SoundCloud (V42-V46) : écoutes, likes, reposts, commentaires sur une ligne ; graphique comparant les sorties sur ces métriques ; « tout le catalogue » : choisir un ou plusieurs titres, comparés en cumulé à âge égal (réutiliser le composant de « sorties à J égal ») ; expliquer le taux d'engagement = (likes + reposts + commentaires) / écoutes ; peu de figures, alignées, la plus utile en haut <!-- critic: non — figures existantes --> <!-- scope: src/dashboard/views/soundcloud.py, src/dashboard/utils/, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest : 4 métriques dans un `st.columns(4)` ; le multi-titres réutilise la fonction de Spotify (un appel, pas une copie) |
| R386 | Rapport de carrière PDF (V47-V51) : section de tête = Accueil, Rapport PDF, Faire piloter mes campagnes ; un filtre « chansons » aligné avec Artiste et Période, défaut toutes, qui remplace « S4A chansons à inclure » et « Focus ML chansons à inclure » ; bouton « dernière sortie » ; bouton Générer juste après les trois filtres ; retirer « Rapport pour … » <!-- critic: non — formulaire et menu --> <!-- scope: src/dashboard/views/export_pdf.py, src/dashboard/utils/nav_sections.py, src/dashboard/utils/pdf_exporter/, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest : 3 filtres sur une ligne puis le bouton ; le PDF généré avec « toutes » contient les sections S4A et ML pour les mêmes titres |
| R387 | Faire piloter mes campagnes (V52-V54) : texte concis « je gère tes campagnes de A à Z selon ton budget et tes objectifs (Meta Ads, créatives, bilan PDF, fichiers quotidiens) », sans durée ni prix ; deux boutons : m'écrire (mail) et réserver un rendez-vous — l'URL de RDV (Calendly ou autre) viendra du propriétaire plus tard : le bouton lit `service_calendly_url`, caché tant qu'elle est vide, tout le reste est livré sans elle <!-- critic: non — texte et liens --> <!-- scope: src/dashboard/views/service.py, src/dashboard/utils/service_offer.py, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest : deux boutons, aucun montant ni durée rendus |
| R388 | Distributeurs (V75-V78) : une seule sous-vue — saisie en haut, toutes années / mois par défaut avec un filtre refait, graphique d'évolution au lieu du tableau détail, point mort en bas, sur la même figure que les prédictions si elle reste lisible <!-- critic: non — mise en page --> <!-- scope: src/dashboard/views/imusician.py, src/dashboard/utils/, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest : plus de `st.tabs` ; le formulaire est le premier widget de la page |
| R389 | SACEM (V79, V80) : graphiques au lieu des tuiles brut / charges / net ; dire que l'import est un fichier `.xlsx` (pas un CSV) et y mener par un bouton vers l'onglet d'import des Credentials <!-- critic: non — figures et lien --> <!-- scope: src/dashboard/views/sacem.py, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest : une figure, un bouton dont la cible est l'onglet d'import |
| R390 | Mon compte (V81-V83) : retirer « Mes comptes branchés » (ils restent dans Credentials) ; sous « Supprimer mon compte », un bouton qui ENVOIE DIRECTEMENT la demande à l'admin par mail (choix du propriétaire 2026-10-05, pas de `mailto`) et dit ce qui va se passer ; mot de passe, 2FA, communications gardés <!-- critic: non — l'envoi passe par la frontière SMTP existante --> <!-- scope: src/dashboard/views/account.py, src/utils/email_alerts.py, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest : le bouton appelle l'envoi une fois (frontière SMTP du conftest) ; « comptes branchés » absent |
| R391 | Facturation (V84-V86) : menu « 💳 Facturation / Abonnement » ; cartes Free et Premium côte à côte, l'inactive barrée, l'active marquée d'une flèche verte, prix mensuel et statut sous chacune ; bouton « Faire piloter mes campagnes » entre les plans et « nos offres » <!-- critic: non — affichage du plan déjà lu --> <!-- scope: src/dashboard/views/billing.py, src/dashboard/utils/nav_sections.py, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest pour un locataire free puis premium : la bonne carte barrée |
| R392 | Export CSV (V87) : le choix ZIP / Excel et « Préparer l'export » en tête de page, téléchargement seulement — tranché 2026-10-05 : pas d'export par mail (il n'en a jamais existé) <!-- critic: non — mise en page --> <!-- scope: src/dashboard/views/export_csv.py, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest : le bouton est le premier widget |
| R393 | Parrainage (V88) : le code de parrainage affiché en clair sous le lien d'activation (aujourd'hui replié dans un expander) ; **pas** de code promo Stripe (reco retenue 2026-10-05 : un code promo se partage hors parrainage, exige une table code→parrain et ouvre une remise au checkout sans inscription) ; à la place, un champ « code de parrainage » FACULTATIF à l'inscription qui rattache le filleul exactement comme le lien — même table, même récompense, mêmes gardes. Suite de R283 <!-- critic: requis — un code saisi rattache un filleul et déclenche une récompense payante --> <!-- scope: src/dashboard/views/referral.py, src/utils/referral_rewards.py, src/api/routers/stripe_webhook.py, src/dashboard/views/billing.py, migrations/, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest : le code est visible hors expander ; un test : le code saisi à l'inscription crée la même ligne de parrainage que le lien ; un code inconnu ou le sien propre est refusé |
| R394 | YouTube Analytics API — INVENTAIRE pour le propriétaire (V40, V41) : liste exhaustive des métriques et dimensions disponibles par vidéo et par chaîne (abonnés gagnés/perdus, durée de visionnage, rétention, sources de trafic, géographie, appareils, revenus si YPP…), le scope OAuth exact, les quotas, ce que chacune permettrait d'afficher, et le geste de branchement ; écrit dans un document neuf de dev-docs (youtube-analytics-inventory) — doc seulement, aucune collecte <!-- critic: non — documentation --> <!-- scope: .claude/dev-docs/ --> | P3 | le document existe, chaque métrique avec son lien de doc officielle ; le propriétaire choisit ce qui entre en roadmap |
| R395 | Déploiement prod en FIN de nuit (autorisé 2026-10-05) : CI verte sur le commit déployé, sauvegarde de la base, migration 145 puis les additives en attente, `deploy.sh` (api + dashboard), `git pull` pour les DAG ; puis contrôles post-déploiement (`/health`, accueil rendu, mails ops) — jamais un DAG déclenché à la main, jamais `tasks test` <!-- critic: non — procédure existante, autorisée --> <!-- scope: .claude/dev-docs/ --> | P2 | HEAD prod = commit déployé ; `/health` 200 ; aucune empreinte neuve dans `app_error_log` 30 min après |
| R397 | Facturation admin — `billing.py:327` appelle `x.strftime` si `x` est vrai : `NaT` (période de fin NULL, laissée par la session Stripe de test) est VRAI → ValueError, la page admin billing plante (2 rouges de `make test-changed` du 2026-10-05) ; + `test_a_first_payment_earns_once_and_the_coupon_lands` rouge sous xdist, vert seul (dépendance d'ordre à trouver) <!-- critic: non — garde d'affichage + isolement de test --> <!-- scope: src/dashboard/views/, tests/, .test_durations --> | P2 | billing rendu avec une période NULL (test qui la sème) ; le test de parrainage vert dans l'ordre de la suite |

---

## ⏸️ R116 — ADR-027, en attente de ses courbes (sortie de l'index 2026-09-17)

**Ni livrée ni abandonnée — parquée sur une mesure, pas archivée.** `archive.md` est
strictement passif (`tests/test_roadmap_two_files.py::test_the_archive_holds_nothing_actionable`
refuse tout item non coché qui y atterrit), donc ce bloc reste ici, hors des deux
index. Sortie de l'index actionnable le 2026-09-17 parce que `daily_ops_metrics` ne
porte qu'**une seule ligne** (2026-09-16), `complete = FALSE`, et **tous ses
percentiles de rendu sont `NULL`** — seul `peak_sessions = 8` est renseigné. La
courbe que R116 exige, `streamlytics_rerun_duration_seconds` côté serveur, n'existe
donc pas encore ; le bloc le disait déjà lui-même : « un ADR écrit avant la mesure
serait une rationalisation ». Déclencheur de réouverture, calculable, dans
`### Conditions d'attente` ci-dessous, ligne « Écrire **ADR-027** (répliques et
Redis) » : `SELECT count(*) FROM daily_ops_metrics WHERE complete` doit rendre
**14 jours** à `TRUE` — **2 en production le 2026-09-20**, et le chiffre écrit ici
disait « 0 » parce qu'il avait été relevé sur la base LOCALE. `make reopen-check-prod`
le remesure ; sans `PROD_SSH` le contrôle rend désormais INDÉCIDABLE plutôt qu'un chiffre
qui ne décrit rien. Elle n'attend aucun geste humain, seulement
du trafic — elle ne va donc pas dans « 🙋 En attente de toi » — et pour la même
raison elle sort de l'ancre de reprise en tête de fichier, qui ne porte que ce que
les deux tables d'index de ce fichier listent encore.

- [ ] **R116 — ADR-027, écrit APRÈS les courbes.**

  ⚠️ **Le numéro a changé** : ce bloc annonçait ADR-026, qui est pris depuis le
  2026-09-16 par la décision d'observabilité. Cette décision-ci est **ADR-027**.

  La décision sur les répliques et sur Redis, avec les DEUX courbes mesurées, les
  alternatives refusées et le déclencheur de relecture. Un ADR écrit avant la mesure
  serait une rationalisation — c'est pourquoi il est une tâche à part et qu'il vient en
  dernier.

  **Il a maintenant de quoi être écrit honnêtement, ce qui n'était pas le cas avant :**
  la réplique est arrêtée côté Caddy ET côté scrutation Prometheus, et les trois gestes
  de remise en service sont écrits en UN seul endroit (le bloc au-dessus de
  `reverse_proxy` dans `deploy/Caddyfile`). La courbe qui tranchera est
  `streamlytics_rerun_duration_seconds`, mesurée côté SERVEUR — insensible à la
  saturation du client, qui est ce qui rendait la mesure de R114 ambiguë.

**Ce qui reste écarté, avec sa raison** : Redis (R113 supprime son besoin pour les
caches, l'étape 1 l'a fait pour les limiteurs — s'il reste un besoin après R114, il sera
NOMMÉ, pas supposé) ; Celery/RQ (Airflow tient l'asynchrone, 13 DAGs) ; Loki et les
traces (après Prometheus, et seulement si un incident les réclame) ; Terraform (0 fichier
IaC, vrai manque — déclencheur : une SECONDE machine, ou une reconstruction subie) ;
S3/MinIO (les deux répliques partagent le même bind-mount sur le même hôte — déclencheur :
une seconde MACHINE) ; MLflow (déclencheur : la première décision de réentraîner) ;
dbt, Kafka, OpenSearch, pgvector, K8s, sharding (déclencheurs calculables d'ADR-014 et
ADR-023, relus le 2026-09-11, aucun tiré).

---

## 🔖 REPRISE — état au 2026-10-04 (à lire EN PREMIER au `/resume`)

<!-- reprise: open=R367, R370, R371, R372, R373, R374, R375, R376, R377, R378, R379, R380, R381, R382, R383, R384, R385, R386, R387, R388, R389, R390, R391, R392, R393, R394, R395, R397, R283 -->

**État au 2026-10-04** : index vide ; seule R283 attend ton geste (🙋). R116 et R131
sont parquées (sections ⏸️), leurs déclencheurs évalués par `make reopen-check` chaque nuit.
Le récit des journées précédentes est dans l'archive (« 🗄️ Historique de l'actif »).

### Conditions d'attente — ce qui n'est PAS une tâche

Motif d'ADR-007 : un travail dont le bénéfice mesuré est nul n'entre pas dans l'index.


| Ce qu'on ne fait pas | Ce qui le rouvrirait, calculable |
|---|---|
| Chercher un 3ᵉ worker pytest en baissant la réserve mémoire | `MemAvailable` au repos dépasse durablement **7 220 Mo** SANS éteindre Airflow — c'est-à-dire si le RAG paresseux tient sa promesse (`ps -eo rss` sur `knowledge-rag` après un redémarrage de session) |
| Retirer les **110 index jamais scannés** (5,7 Mo) | une table de faits dépasse **1 M lignes** — l'amplification d'écriture devient réelle. Aujourd'hui : 34 078. `SELECT max(n_live_tup) FROM pg_stat_user_tables` |
| Sortir **Airflow** de la boîte (il prend 2,3 Go des 7,7) | la RAM des conteneurs dashboard dépasse **2 Go** — ce que R87 rapproche. `docker stats --no-stream` |
| Construire la **couche or** (table de faits agrégée) | un locataire dépasse **100 000 lignes** sur une table de faits, ou un agrégat d'accueil dépasse **200 ms**. Aujourd'hui : 14 694 lignes, 46 ms |
| ClickHouse / Parquet / dbt / Dagster | déclencheurs d'**ADR-014**, relus le 2026-09-11 : aucun n'est tiré (62 Mo contre 50 Go, 34 k lignes contre 10 M) |
| Écrire **ADR-027** (répliques et Redis) | `daily_ops_metrics` porte **14 jours `complete = TRUE`** : `SELECT count(*) FROM daily_ops_metrics WHERE complete` — **aujourd'hui 0**. La table a UNE ligne (2026-09-16), `complete = FALSE`, et **tous ses percentiles de rendu sont `NULL`** ; seul `peak_sessions = 8` est renseigné. La courbe qui doit trancher — `streamlytics_rerun_duration_seconds` côté serveur, et `streamlytics_reruns_in_flight` pour la saturation — n'existe donc pas encore. Le bloc de R116 le disait lui-même : *« un ADR écrit avant la mesure serait une rationalisation »*. Ce n'est pas du travail en retard, c'est du temps et du trafic |
| Fragmenter les **5 vues restantes** de R118 — `imusician`, `meta_ads_overview`, `hypeddit`, `youtube`, `admin` | l'une d'elles dépasse **300 ms de vue** dans l'histogramme SERVEUR : `histogram_quantile(0.5, sum by (page,le) (rate(streamlytics_rerun_duration_seconds_bucket{phase="view"}[1h])))`. Mesuré localement le 2026-09-17 : 20 à 130 ms de rerun à chaud, **dans la même bande que les six déjà fragmentées** (78 à 172 ms) — donc rien ne les distingue, et le bruit local (±60 à 100 %) est plus large que les écarts. Seul le serveur peut trancher, et il lui faut du trafic sur ces pages |

📥 **Erreurs applicatives non triées : 0** — `.claude/dev-docs/error-inbox.md`, régénéré par `make error-inbox`. Ce fichier est écrit par une machine ; aucune tâche n'en sort toute seule.
<!-- error-inbox: open=0 -->

---

## ⏸️ R131 — Calibrer les trois seuils de charge (sortie de l'index 2026-09-17)

**Ni livrée ni abandonnée — parquée sur une mesure, pas archivée.** `archive.md` est
strictement passif (`tests/test_roadmap_two_files.py::test_the_archive_holds_nothing_actionable`
refuse tout item non coché qui y atterrit), donc ce bloc reste ici, hors des deux index.

**Pourquoi elle sort de l'index actionnable** : elle demande de dériver trois seuils sur
une distribution, et la distribution n'existe pas. Mesuré le 2026-09-17 :
`daily_ops_metrics` porte **1 ligne en production** (2026-09-17) et 2 en local. Il en
faut 30. Aucun geste ne la débloque — seulement du trafic et du temps —, donc elle ne va
pas non plus dans « 🙋 En attente de toi ».

Écrire les seuils maintenant serait exactement le défaut que la règle interdit : le dépôt
porte déjà **cinq** seuils sans dérivation (disque 85 %, RAM 500 Mo, sauvegarde 25 h,
watchdog 26 h / 48 h), plus le 20 de `scale_check.sh`, posé face à un pic observé de 12
sans que le facteur 1,7 soit justifié.

**Déclencheur de réouverture, calculable** :

```sql
SELECT count(*) FROM daily_ops_metrics WHERE day > now() - interval '30 days';
-- doit rendre 30 — **4 en production le 2026-09-20**
-- ⚠️ À mesurer EN PRODUCTION : `make reopen-check-prod PROD_SSH=…`. Le « 1 » écrit ici
-- venait de la base locale, et l'outil de réouverture faisait la même erreur jusqu'au
-- 2026-09-20 (il annonçait 5).
```

- [ ] **R131 — les trois seuils de charge, dérivés d'une distribution et non d'un instinct.**

| règle différée | ce qu'elle surveillerait | la grandeur qui existe déjà |
|---|---|---|
| `SessionsHigh` | la charge utilisateur | `streamlytics_sessions_1m`, `daily_ops_metrics.peak_sessions` |
| `ErrorRateHigh` | une pointe d'erreurs | `streamlytics_app_errors_total`, `errors_by_page` |
| `LogErrorBurst` | une pointe de journaux ERROR | `streamlytics_log_records_total{level="ERROR"}` |

⚠️ Les quatre alertes livrées le 2026-09-17 ne portent **aucun** seuil — `absent()`,
`up == 0`, `read_ok == 0`. Elles couvrent le silence des instruments, pas la charge. Les
deux questions sont distinctes et la seconde attend ses données.

---

## 🙋 En attente de toi (aucune ne se débloque sans une action humaine)

Elles restent comptées comme ouvertes — rien n'est supprimé — mais elles ne sont pas dans
l'index ci-dessus parce qu'aucune ne peut commencer sans toi. Chacune dit exactement quel
geste elle attend.

📋 **Procédures pas à pas, avec leur vérification :
`.claude/dev-docs/runbook-actions-utilisateur.md`** — classées par ce qu'elles
débloquent, chacune avec la commande qui prouve que c'est fait. `tests/test_roadmap_index_is_honest.py`
échoue si une ligne d'ici n'a pas sa section là-bas.

| id | tâche | prio | le geste qu'elle attend |
|----|-------|------|--------------------------|
| R283 | Parrainage Stripe (R272, actif en prod) : créer le coupon « 1 mois offert » (100 %, une fois) en mode test puis live, poser `STRIPE_REFERRAL_COUPON_ID` sur le serveur, abonner le webhook à `invoice.paid`, `charge.refunded` et `charge.dispute.created`, puis rejouer un parrainage en mode test | P2 | ta vérification — runbook § 39 |
