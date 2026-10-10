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
| R501 | iMusician lit une colonne ENTIÈRE comme 0 dès qu'une cellule est vide : pandas la passe en float et `_clean_numeric(3.0, int)` fait `int("3.0")` ⇒ 0 (trouvé par la passe Hypothesis du 2026-10-10, vérifié par appel) ; balayer `int(str(x))` sur une colonne pandas <!-- critic: non — correctif local, propriété mutée --> <!-- scope: src/transformers/, tests/, .test_durations, .claude/dev-docs/ --> | P1 | propriété int/float/NaN/texte rouge avant, verte après ; prod `_clean_numeric(3.0, int) == 3` |
| R502 | Une valeur ILLISIBLE n'est plus lue 0 en silence : les lecteurs comptent les rejets par colonne (ligne, colonne, texte brut), l'import les affiche et les écrit dans `csv_upload_log` (à côté de `serialization`), une colonne > 5 % illisible refuse le fichier en la nommant ; `upload_csv.py:338` (`to_numeric().fillna(0)`) passe par le lecteur partagé — vide/`-` reste 0 légitime <!-- critic: requis — contrat d'import + migration additive --> <!-- scope: src/transformers/, src/dashboard/views/upload_csv.py, src/dashboard/utils/, src/dashboard/i18n/, migrations/, init_db.sql, tests/, .test_durations, .claude/dev-docs/ --> | P2 | un fichier à valeurs illisibles affiche leur nombre ; export FR « 1 234 » accepté |
| R503 | La locale d'un nombre se décide par FICHIER : `csv_dialect.read_number(text, decimal)` pour les cinq lecteurs, décimale déduite du séparateur détecté — « 1.234,5 » rend 1234,5 (aujourd'hui 1, 0 ou 0.0 selon le lecteur) <!-- critic: non — fonction pure, propriété aller-retour avec formats.num --> <!-- scope: src/transformers/, src/dashboard/views/upload_csv.py, tests/, .test_durations, .claude/dev-docs/ --> | P2 | `read_number(formats.num(x, lang), decimal(lang)) == x` |
| R504 | Bornes : `entry_period.resolve` rend fin < début pour une sortie future et 29 j pour « 28 j » ; `valider_montant` lève une `ValueError` brute sur « ² » et ignore `\xa0` ; `validate_columns` laisse passer tout ce qui commence par `(` et `"abc\n"` (`$` au lieu de `fullmatch`) <!-- critic: non — validations locales, propriétés mutées --> <!-- scope: src/dashboard/utils/, src/database/postgres_handler.py, tests/, .test_durations, .claude/dev-docs/ --> | P2 | fin ≥ début ; N jours = N jours ; hors allowlist ⇒ refus |
| R505 | 2ᵉ vague de propriétés Hypothesis : dédoublonnage DistroKid/iMusician conserve les totaux, `upsert_many` ne fusionne que des clés égales, `platform_chart._aggregate` partitionne les jours, `non_overlapping_cover` sans recouvrement, `track_title_matches` symétrique <!-- critic: non — tests seuls, chaque propriété mutée --> <!-- scope: tests/, src/, .test_durations, .claude/dev-docs/ --> | P2 | chaque propriété rougit sur sa mutation |
| R506 | Ne plus exiger un document régénéré qui ne sert à personne : retirer la porte des durées (pytest-split donne la moyenne à un test inconnu ; rafraîchir `.test_durations` à la demande), registre des graphiques en avertissement, compte d'en-tête du catalogue calculé, lecteurs de gouvernance ciblés, les tests n'écrivent plus dans le journal réel des refus (26 `probe` en 7 j) <!-- critic: requis — retire des portes --> <!-- scope: .pre-commit-config.yaml, tools/, tests/, .github/workflows/, Makefile, .claude/, .test_durations, CLAUDE.md --> | P3 | REFUS 7 j sans `test-durations-missing` ; 0 refus `probe` |
| R507 | Dependabot casse la CI 5 fois en 14 j (pyproject et requirements montés, `uv.lock` non) : écosystème `uv` <!-- critic: non — configuration --> <!-- scope: .github/, .claude/dev-docs/ --> | P3 | prochaine PR Dependabot verte sans retouche |
| R508 | Cibles `make` : 97 cibles (CLAUDE.md en annonce 11), 30 jamais lancées, 7 disparues encore appelées, 15 hors `.PHONY`, `lint` ≠ CI ; `make help` en sections, cibles `ci-wait`/`test-verdict`/`suite-status`/`psql`/`ARGS=`, `SUITE_SCOPE` qui dit quand le plafond mémoire est inactif, garde « aucune cible appelée n'est absente » <!-- critic: non — outillage, garde muté --> <!-- scope: Makefile, tools/, tests/, CLAUDE.md, .claude/, .test_durations --> | P3 | `make help` = liste de CLAUDE.md ; 0 cible fantôme appelée |

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

<!-- reprise: open=R501,R502,R503,R504,R505,R506,R507,R508 -->

**État au 2026-10-10 (nuit)** : R501-R508 — passe défauts produit (Hypothesis : iMusician P1, rejets comptés, locale par fichier, bornes), propriétés vague 2, portes de documents allégées, Dependabot uv, cibles make ; études E1-E6 dans `.claude/dev-docs/studies/`. **État au 2026-10-10 (soir)** : R497-R500 — moins de rouges auto-infligés (analyse : 42 % des ids testent le processus, 1 rouge CI sur 15 est un défaut produit) : porte des durées, deux voies, pilote Hypothesis, admission du catalogue. **État au 2026-10-10** : R494-R496 — restes vivants des balayages de R493 et R495 (résolution d’imports au nom importé ; un plantage n’est pas un verdict ; déclencheur p50 non lu). **État au 2026-10-09** : 2ᵉ lot de retours vocaux (W1-W14, `revue/notes-vocales-2026-10-09.md`) → R474-R489, à faire en séance de nuit dans l'ordre de l'index (bugs P2/P3, puis les deux vues réceptrices R476/R477 et le filtre commun R478, puis vue par vue). Avant :  retours vocaux du propriétaire sur l'app → R437-R443 (assistant, mapping, saisie S4A, Hypeddit), toutes livrées et déployées le 2026-10-07 (R442 en option A : le pari du modèle est un onglet admin, les grilles restent chez l’artiste). R116 et R131
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
