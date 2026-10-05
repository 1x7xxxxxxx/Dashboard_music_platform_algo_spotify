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
| R408 | R283 en prod : `STRIPE_REFERRAL_COUPON_ID` posé dans `.env` n'atteint ni l'api ni le dashboard — le compose ne le passe pas (`environment:` explicite, pas d'`env_file`). Le câbler (modèle versionné + prod), balayer les autres variables lues et jamais passées, et un garde qui rapproche `os.getenv` du compose <!-- critic: non — câblage de configuration, garde neuf muté --> <!-- scope: docker-compose.example.yml, .env.example, src/utils/referral_rewards.py, deploy/, tests/, .test_durations, .claude/dev-docs/ --> | P2 | `coupon_set= True` dans les deux conteneurs ; garde rouge sur le modèle d'avant |
| R409 | R406(1) : le panneau « 🎂 Quelle tranche d'âge clique le moins cher » quitte le CPR Optimizer (Premium) pour la Vue croisée (Free) — donnée déjà visible dans Meta Ads, décision du propriétaire 2026-10-05. L'affinité d'âge reste dans le score Premium <!-- critic: non — déplacement d'un rendu existant --> <!-- scope: src/dashboard/views/meta_cpr_optimizer.py, src/dashboard/views/meta_ads_overview.py, src/dashboard/utils/, src/dashboard/content/chart_decisions.py, tools/dev/charts_dossier/, tests/, .test_durations, .claude/dev-docs/ --> | P3 | AppTest des deux vues + PNG regardé ; `chart_decisions` à jour |
| R410 | R406(2) : l'aperçu algo gratuit liste les critères manquants / imputés, sans les contributions SHAP (réservées Premium) <!-- critic: non — filtrage d'un rendu existant --> <!-- scope: src/dashboard/views/trigger_algo/, src/dashboard/utils/, tests/, .test_durations, .claude/dev-docs/ --> | P3 | AppTest free/premium : aucune contribution chiffrée en free |
| R411 | Harnais : fermer les défauts `test_red` périmés (tests re-rejoués verts) et lire le traceback `render_harness` ouvert <!-- critic: non — tri --> <!-- scope: .claude/dev-docs/, tools/dev/, tests/, .test_durations --> | P4 | `make defect-log` à 0 ouvert, ou chacun nommé |
| R412 | Harnais : re-muter les 14 preuves `seen_red` périmées et muter REQ-BRONZE-02 (vert jamais vu rouge) <!-- critic: non — mesure --> <!-- scope: .claude/dev-docs/, tools/dev/, tests/, .test_durations, .claude/scripts/ --> | P4 | `make harness-report` : 0 périmée, 0 vert-jamais-rouge |
| R413 | Harnais : les 3 commandes orphelines (`review-architecture`, `review-dag`, `review-db-schema`) archivées ou nommées par un déclencheur ; REQ-HARN-11/13 tranchés <!-- critic: non — rangement --> <!-- scope: .claude/commands/, archive/, .claude/dev-docs/, tools/dev/, tests/, .test_durations --> | P4 | `make harness-report` : 0 orpheline |
| R414 | Harnais : REQ-HARN-04 (hooks PostToolUse fusionnés en un processus) et REQ-HARN-06 (night-status écrit dans le fichier de séance) <!-- critic: requis — touche le chemin de chaque édition --> <!-- scope: .claude/hooks/, .claude/settings.json, tools/dev/, tests/, .test_durations, .claude/dev-docs/ --> | P4 | latence mesurée avant/après, en alternance |
| R415 | Harnais : fraîcheur des workflows planifiés (voisin de R407) — un cron GitHub qui ne tourne plus se voit dans night-check <!-- critic: non — contrôle additif --> <!-- scope: tools/dev/, .github/workflows/, tests/, .test_durations, .claude/dev-docs/ --> | P4 | garde muté rouge sur un run vieux de > 2 périodes |

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

<!-- reprise: open=R283, R406, R408, R409, R410, R411, R412, R413, R414, R415 -->

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
| R406 | Deux décisions de TARIF sorties de R399 et R381 (2026-10-05) : (1) « quelle tranche d'âge clique le moins cher » quitte le CPR Optimizer (Premium) pour la Vue croisée (Free) ? (2) l'aperçu gratuit montre-t-il un SHAP des valeurs imputées (expose une partie du modèle Premium) ? | P3 | ta réponse dans le fil — runbook § 40 |
