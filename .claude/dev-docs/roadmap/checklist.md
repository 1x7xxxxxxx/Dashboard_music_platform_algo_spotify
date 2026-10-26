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
| R642 | Les 4 domaines orphelins de `REQUIREMENTS-COVERAGE.md` (`ml`, `product-offer`, `pc-perf` : une exigence chacun, prouvée par un test existant ; `rag-knowledge` : exemption écrite, rien du domaine n'est dans le dépôt) — baseline T217 — msg:1792186131629305594-522497, msg:1792239848166396738-2859448 — **livré 2ecf73d4 (2026-10-21)** ; reste : rejouer `make requirements-report` (orphelins 0) puis fermer. REQ-ORCH-03 / REQ-RUN-04 restent « absent », différés par ADR-030 sous R284 — hors de cette ligne <!-- critic: non — catalogue de données, preuves = tests existants rejoués --> <!-- scope: .claude/dev-docs/architecture/, REQUIREMENTS-COVERAGE.md, tests/test_every_requirement_has_a_probe.py --> | P3 | `make requirements-report` → orphelins : 0 (exit 0) |
| R643 | `make test` rouge hors terminal interactif (fleet-verify baseline T364, 2026-10-23 : 2 échecs) — `check_mermaid` trouve mmdc par le repli nvm mais le lance sans `node` dans le PATH (exit 2 « renderer unavailable ») ; `test_the_signup_field_is_optional_and_prefilled_from_the_link` dépend de la base vivante sans la déclarer (`project_db()` arrête la page) — msg:1792189738671553422-1559504, msg:1792681020848237514-1667173, msg:1792672621652191236-1207955 (suite rouge) — **livré bdf84e96 + ea333d16** ; reste : la mesure (PATH minimal, `docker stop postgres_spotify_airflow`, les deux tests, puis `docker start`), un `make test` complet, puis `git stash show` et abandon de `stash@{0}` (test-suite-timing.json, ère R652) et `stash@{1}` (ère R403) s'ils ne portent rien d'autre <!-- critic: non — deux défauts d'environnement de test, cause mesurée, aucun code produit --> <!-- scope: .claude/scripts/check_mermaid.py, tests/test_every_mermaid_block_renders.py, tests/test_the_referral_code_is_shown_in_clear.py, .claude/dev-docs/test-suite-timing.json --> | P3 | `env PATH=/usr/bin:/bin .venv/bin/python -m pytest tests/test_every_mermaid_block_renders.py tests/test_the_referral_code_is_shown_in_clear.py` vert, base arrêtée ; puis `make test` vert |
| R649 | Norme RQ des rapports, partie constructible (code-critic 2026-10-26 : BUILD-MODIFIED) — (A) `guide_pdf` : rendu dans un fichier temporaire → `report_quality.py --kind guide --strict` → seulement alors déplacement + `.guide_fingerprint` ; précondition make qui nomme le correctif si le vérificateur ou `pdftotext` manque ; `test_the_shipped_guide_is_the_current_guide.py` score aussi les PDF commités ; RQ-8 de la version EN (26 % > 25 %) corrigé en coupant du remplissage, pas en ajoutant des chiffres. (C) `charts_dossier` : page de tête qui énonce les décisions de `triage.py`/`actions.yaml` (chiffres lus dans capture.json, jamais tapés), gate en fin de `main.py` (couvre aussi `--rebuild`), pas de test CI (PDF hors dépôt, données d'artiste). Le dossier d'architecture et `pdf_exporter` → R661 — msg:1792366598159790086-2236949 <!-- critic: fait 2026-10-26 — BUILD-MODIFIED (A, C) --> <!-- scope: tools/dev/architecture_dossier/, tools/dev/charts_dossier/, src/dashboard/guides/, tests/ --> | P3 | `report_quality.py --strict` → 0 sur les 2 guides (`--kind guide`) et le dossier des graphiques ; `make guide` sort ≠ 0 sur un guide qui échoue |
| R653 | `docs/CADRAGE.md` : remplir les 7 parties « à compléter » avec ce que le dépôt sait — msg:1792935864452958142-51378, msg:1792935997053644629-683774, msg:1792952645167978110-3858378 — Besoin à écrire depuis ADR-025 (chiffres éparpillés S4A/Meta/Instagram/Hypeddit/Shazam), ADR-028 (critère = activation, `src/utils/activation.py`, R149) et `runbook-artist-test-session.md` ; puis tableau des risques, ATAM, Méthode ; et `mesure:` manquant sur O1–O4 de `docs/architecture/objectives.yaml` (lu par project_brief.py) ; P4 : seulement après R659 <!-- critic: non — document de cadrage --> <!-- scope: docs/CADRAGE.md, docs/architecture/objectives.yaml --> | P4 | `grep -c "à compléter" docs/CADRAGE.md` → 0 |
| R657 | generated-freshness : en-têtes rejouables de `error-family-rules.md`, `error-inbox.md`, `schema-drift-2026-06-13.md`, `REQUIREMENTS-COVERAGE.md`, `ROADMAP-HEALTH.md` (commandes qui tournent hors du vrai HOME) — msg:1792725969026398388-2318692, msg:1792952645167978110-3858378 — **livré 472323d4 + 0dbe364c** (STATEFUL + `--write` acceptés) ; reste : fermer avec le résidu écrit — `error-inbox.md` ne se rejoue pas hors machine (copie du lecteur sans config gitignorée, limite du maître, kind `machine`) ; REQUIREMENTS-COVERAGE relève de R642 <!-- critic: non — en-têtes de documents générés --> <!-- scope: .claude/dev-docs/, docs/, tools/, REQUIREMENTS-COVERAGE.md, Makefile --> | P4 | `fleet_apply.py plan` sans « generated-freshness » |
| R663 | L'ancien chemin du dépôt (`/home/timothe/streamlytics`, déménagé vers `~/projects/` ~2026-10-20) vit encore : 20 replis `|| echo /home/timothe/streamlytics` dans `.claude/settings.json` (un hook lancé hors dépôt vise un chemin mort), et des conteneurs compose (projet `dashboard_music_platform_algo_spotify`) peuvent monter l'ancien chemin — postgres l'a fait (Docker y a créé un dossier vide, recréé le 2026-10-26) ; les shebangs de `.venv`/`.audit-venv` sont réparés (R660). Ajouter un garde qui lit les deux surfaces (trouvé pendant R660) <!-- critic: non — remplacement de chemin + garde ciblé --> <!-- scope: .claude/settings.json, tests/, docker-compose.yml --> | P3 | `grep -c '/home/timothe/streamlytics' .claude/settings.json` → 0 ; `docker inspect $(docker ps -aq) --format '{{range .Mounts}}{{.Source}} {{end}}' \| grep -c '/home/timothe/streamlytics/'` → 0 |
| R664 | Journal des défauts : 13 ouverts (6 test_red, 7 traceback) et 15 billets `recurrence:` à confirmer, annoncés à chaque démarrage de séance — trier chacun (fermer avec sa cause, ou ouvrir sa ligne) (trouvé à la reprise du 2026-10-26) <!-- critic: non — tri --> <!-- scope: .claude/dev-docs/, tools/dev/, tests/test_the_referral_code_is_shown_in_clear.py --> | P3 | `make defect-log` → 0 défaut ouvert non trié |

---

---

## 🔖 REPRISE — état au 2026-10-04 (à lire EN PREMIER au `/resume`)

<!-- reprise: open=R642, R643, R649, R653, R657, R663, R664, R661, R662 -->
**État au 2026-10-10 (fin de nuit)** : toutes les recos portées en roadmap — R507 tranchée (a), R509 mutmut, R510 inachevés, R511 YouTube Analytics. **État au 2026-10-10 (nuit)** : R501-R508 — passe défauts produit (Hypothesis : iMusician P1, rejets comptés, locale par fichier, bornes), propriétés vague 2, portes de documents allégées, Dependabot uv, cibles make ; études E1-E6 dans `.claude/dev-docs/studies/`. **État au 2026-10-10 (soir)** : R497-R500 — moins de rouges auto-infligés (analyse : 42 % des ids testent le processus, 1 rouge CI sur 15 est un défaut produit) : porte des durées, deux voies, pilote Hypothesis, admission du catalogue. **État au 2026-10-10** : R494-R496 — restes vivants des balayages de R493 et R495 (résolution d’imports au nom importé ; un plantage n’est pas un verdict ; déclencheur p50 non lu). **État au 2026-10-09** : 2ᵉ lot de retours vocaux (W1-W14, `revue/notes-vocales-2026-10-09.md`) → R474-R489, à faire en séance de nuit dans l'ordre de l'index (bugs P2/P3, puis les deux vues réceptrices R476/R477 et le filtre commun R478, puis vue par vue). Avant :  retours vocaux du propriétaire sur l'app → R437-R443 (assistant, mapping, saisie S4A, Hypeddit), toutes livrées et déployées le 2026-10-07 (R442 en option A : le pari du modèle est un onglet admin, les grilles restent chez l’artiste). R116 (ADR-027) et R131
(seuils de charge dérivés par Prometheus) sont livrées le 2026-10-12 : plus aucun bloc ⏸️.
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
| Fragmenter les **5 vues restantes** de R118 — `imusician`, `meta_ads_overview`, `hypeddit`, `youtube`, `admin` | l'une d'elles dépasse **300 ms de vue** dans l'histogramme SERVEUR : `histogram_quantile(0.5, sum by (page,le) (rate(streamlytics_rerun_duration_seconds_bucket{phase="view"}[1h])))`. Mesuré localement le 2026-09-17 : 20 à 130 ms de rerun à chaud, **dans la même bande que les six déjà fragmentées** (78 à 172 ms) — donc rien ne les distingue, et le bruit local (±60 à 100 %) est plus large que les écarts. Seul le serveur peut trancher, et il lui faut du trafic sur ces pages |

📥 **Erreurs applicatives non triées : 0** — `.claude/dev-docs/error-inbox.md`, régénéré par `make error-inbox`. Ce fichier est écrit par une machine ; aucune tâche n'en sort toute seule.
<!-- error-inbox: open=0 -->

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
| R661 | Norme RQ — deux questions de produit sorties de R649 : (1) le dossier d'architecture (33 p., 6 625 mots, score 2/8 en `decision`) ne porte AUCUNE décision ouverte — l'exempter des règles RQ-1 à RQ-4 comme document de référence (écrit dans son README), ou lui écrire une feuille de décision ? (2) le PDF artiste (`pdf_exporter`) doit-il passer la norme ? <!-- critic: non — question au propriétaire --> <!-- scope: .claude/dev-docs/runbook-actions-utilisateur.md --> | P3 | répondre (1) exempter / feuille, (2) oui / non — runbook § 46 |
| R662 | Mails ops non triés depuis le 2026-10-16 (journal vieux de 10 j) : le connecteur Gmail demande une ré-authentification <!-- critic: non — question au propriétaire --> <!-- scope: .claude/dev-docs/runbook-actions-utilisateur.md --> | P3 | `/mcp` → Gmail → se reconnecter ; ensuite le tri `from:noreply@streamlytics.fr after:2026/10/16` se fait en séance — runbook § 47 |
