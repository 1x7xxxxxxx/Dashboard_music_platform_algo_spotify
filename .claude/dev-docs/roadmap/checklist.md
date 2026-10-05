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
| R399 | Vue croisée — UN jeu de filtres (suite de R378) : compte, campagne, période en tête de page, lus par chaque section ; la période SUIT la campagne quand une campagne est choisie (`_campaign_window`), libre sur « toutes » ; Instagram organique hors compte/campagne, dit à l'écran ; filtre de données = widget dont la valeur atteint SQL ou `.isin`, tout autre widget allowlisté par clé avec raison ; rapatrier « quelle tranche d'âge clique le moins cher » (CPR Optimizer, Premium) — **à trancher par le propriétaire : il passerait en Free** <!-- critic: requis — fait 2026-10-05 avec R378 (BUILD-MODIFIED), points 1-5 --> <!-- scope: src/dashboard/views/meta_ads_overview.py, src/dashboard/views/meta_x_spotify.py, src/dashboard/views/meta_creatives.py, src/dashboard/views/meta_breakdowns.py, src/dashboard/views/instagram.py, src/dashboard/views/meta_cpr_optimizer.py, src/dashboard/views/home_meta_advice.py, src/dashboard/utils/, docs/adr/, .claude/dev-docs/, tests/, .test_durations --> | P3 | un test AST : aucun selectbox/multiselect/segmented_control/filtre de période hors de la barre, sauf allowlist par clé ; un rendu : un widget compte, campagne, période |
| R380 | Vue algo UNIQUE — structure (V18, V20, V57-V63, V65, V67-V69, V73, V74) : les 4 onglets de « Prédiction déclenchement » fusionnés en une page lue de haut en bas, avec séparateurs ; elle absorbe Paramètres de mes campagnes, Prévisions revenus (+ « où j'en suis vs somme des dépenses »), « Résultats réalisés » et « Le pari du modèle » de la saisie S4A ; jauges 0-100 gardées, noms de playlist en pastilles ; retirer « prochain geste titre par titre » et « vrai pour tout ton catalogue » ; « valeurs qui déclencheraient » : 2 titres, en graphiques ; Budget & ROI en graphiques ; ordre DW → Radio → RR PARTOUT (aujourd'hui DW·RR·Radio ici, RR·DW·Radio au budget) ; « Comment lire » réécrit (il décrit 7 onglets qui n'existent plus — défaut trouvé). Section Premium = Aperçu + cette vue <!-- critic: requis — fusion de 4 pages Premium, ce que l'abonnement vend --> <!-- scope: src/dashboard/views/trigger_algo/, src/dashboard/views/meta_campaign_settings.py, src/dashboard/views/revenue_forecast.py, src/dashboard/views/saisie_s4a.py, src/dashboard/views/algo_preview.py, src/dashboard/utils/, src/dashboard/routes.py, src/dashboard/app.py, src/database/stripe_schema.py, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | section Premium = 2 entrées ; AppTest : aucun `st.dataframe` hors expander de détail ; une constante d'ordre DW/Radio/RR lue par toutes les figures |
| R381 | Vue algo — le contenu qui décide (V56, V64, V66, V71, V72) : SHAP par playlist en ordre décroissant, valeur atteinte vs valeur nécessaire, avec les seuils Spotify (deux jeux divergent : 130/137/639 dans le guide, 417/1333/8423 au budget — même grandeur ou deux notions, à lire dans le code) ; coût Meta pour combler l'écart au meilleur CPR et au CPR moyen ; recommandations détaillées du CPR Optimizer pour la dernière sortie ; réglages recommandés tirés des campagnes au meilleur CPR (âge, placement…) avec ce qui change ; aperçu gratuit : un SHAP des valeurs manquantes <!-- critic: requis — des recommandations et des montants que l'artiste applique --> <!-- scope: src/dashboard/views/trigger_algo/, src/dashboard/views/algo_preview.py, src/dashboard/views/meta_cpr_optimizer.py, src/dashboard/views/meta_campaign_settings.py, src/dashboard/utils/, src/ml/, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | un test : seuils lus d'UNE constante ; le coût pour combler sort de la fonction partagée avec l'accueil (R372) ; recommandations calculées sur un jeu de campagnes fixé, rouges si le meilleur CPR change |
| R388 | Distributeurs (V75-V78) : une seule sous-vue — saisie en haut, toutes années / mois par défaut avec un filtre refait, graphique d'évolution au lieu du tableau détail, point mort en bas, sur la même figure que les prédictions si elle reste lisible <!-- critic: non — mise en page --> <!-- scope: src/dashboard/views/imusician.py, .claude/dev-docs/first-screen-ceilings.json, tools/dev/charts_dossier/, src/dashboard/content/, src/dashboard/utils/, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest : plus de `st.tabs` ; le formulaire est le premier widget de la page |
| R391 | Facturation (V84-V86) : menu « 💳 Facturation / Abonnement » ; cartes Free et Premium côte à côte, l'inactive barrée, l'active marquée d'une flèche verte, prix mensuel et statut sous chacune ; bouton « Faire piloter mes campagnes » entre les plans et « nos offres » <!-- critic: non — affichage du plan déjà lu --> <!-- scope: src/dashboard/views/billing.py, src/dashboard/utils/nav_sections.py, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest pour un locataire free puis premium : la bonne carte barrée |
| R393 | Parrainage (V88) : le code de parrainage affiché en clair sous le lien d'activation (aujourd'hui replié dans un expander) ; **pas** de code promo Stripe (reco retenue 2026-10-05 : un code promo se partage hors parrainage, exige une table code→parrain et ouvre une remise au checkout sans inscription) ; à la place, un champ « code de parrainage » FACULTATIF à l'inscription qui rattache le filleul exactement comme le lien — même table, même récompense, mêmes gardes. Suite de R283 <!-- critic: requis — un code saisi rattache un filleul et déclenche une récompense payante --> <!-- scope: src/dashboard/views/referral.py, src/utils/referral_rewards.py, src/api/routers/stripe_webhook.py, src/dashboard/views/billing.py, migrations/, tests/, .test_durations, src/dashboard/utils/i18n_catalog/ --> | P3 | AppTest : le code est visible hors expander ; un test : le code saisi à l'inscription crée la même ligne de parrainage que le lien ; un code inconnu ou le sien propre est refusé |
| R395 | Déploiement prod en FIN de nuit (autorisé 2026-10-05) : CI verte sur le commit déployé, sauvegarde de la base, migration 145 puis les additives en attente, `deploy.sh` (api + dashboard), `git pull` pour les DAG ; puis contrôles post-déploiement (`/health`, accueil rendu, mails ops) — jamais un DAG déclenché à la main, jamais `tasks test` <!-- critic: non — procédure existante, autorisée --> <!-- scope: .claude/dev-docs/ --> | P2 | HEAD prod = commit déployé ; `/health` 200 ; aucune empreinte neuve dans `app_error_log` 30 min après |
| R398 | Constats MEDIUM de l'audit sécurité de R370 (2026-10-05) : (a) `locked_until` lu AVANT bcrypt → une rafale parallèle obtient 4 + N essais par fenêtre — prendre la tentative atomiquement avant bcrypt (`UPDATE … WHERE locked_until IS NULL OR <= NOW() RETURNING id`), dashboard et API ; (b) le défi TOTP du dashboard ne relit pas `locked_until` — un code juste lève le verrou ; (c) `update_platform_secret` rend None en silence quand il refuse d'écrire (blob illisible, lock_timeout) — un refresh_token SoundCloud neuf est perdu alors que l'ancien est révoqué : lever, et faire échouer la tâche appelante <!-- critic: requis — chemin d'authentification et de secret --> <!-- scope: src/dashboard/auth.py, src/api/auth.py, src/utils/login_lockout.py, src/utils/credential_loader.py, src/collectors/, airflow/dags/, tests/, .test_durations --> | P2 | (a) test de rafale : 8 essais parallèles, ≤ 5 vérifications bcrypt ; (b) code juste pendant le verrou → refusé ; (c) un refus d'écriture fait échouer l'appelant |

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

<!-- reprise: open=R399, R380, R381, R388, R391, R393, R395, R398, R283 -->

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
