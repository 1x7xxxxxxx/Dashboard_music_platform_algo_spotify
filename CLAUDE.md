# CLAUDE.md

## Project Overview

**streaMLytics** — Multi-tenant music analytics SaaS. ELT pipeline: external APIs and CSVs → Airflow DAGs (Docker) → PostgreSQL `spotify_etl` → Streamlit dashboard. Sources: Spotify API, Spotify for Artists CSV, Meta Ads, YouTube, SoundCloud, Instagram, Apple Music.

## Architecture

### Data Flow
External APIs / CSV files → Airflow DAGs (Docker) → PostgreSQL `spotify_etl` (port 5433 locally) → Streamlit Dashboard (port 8501).

### Docker Services
**postgres** (PostgreSQL 17, 5433→5432 ; `airflow_db` + `spotify_etl`) · **airflow-webserver** (http://localhost:8080) · **airflow-scheduler** (picks up `airflow/dags/`) · **airflow-init** (one-shot DB init + admin user).

`src/` and `airflow/dags/` are volume-mounted into containers — changes go live without rebuild.

### Source Layout
```
src/
  collectors/   # API clients (spotify, youtube, soundcloud, instagram, meta, s4a)
  transformers/ # CSV parsers (s4a, apple_music, meta_csv, meta_insight)
  database/     # PostgresHandler + per-platform schema definitions
  models/       # Pydantic validators (meta_ads_validators)
  utils/        # config_loader, airflow_trigger, email_alerts, error_handler, retry,
                # metrics.py (Prometheus), ops_alerts.py, daily_ops_metrics.py (en base)
  api/          # FastAPI REST (JWT) — expose `/metrics` sur SON port HTTP (ADR-026)
  dashboard/
    serve.py    # ⚠️ L'ENTRÉE DU CONTENEUR — exportateur de métriques PUIS `streamlit run`,
                #    même processus (un `&` exposerait un registre vide)
    app.py      # Streamlit entry point + routing (lancé PAR serve.py en conteneur)
    views/      # One file per page
    utils/      # get_db_connection, airflow_monitor ; fragment_db.py (un `@st.fragment`
                # RÉUTILISE la connexion de la page), metrics_seam.py (rerun → métriques)

airflow/
  dags/         # Production DAGs (live-mounted)
```

### Database
`PostgresHandler` (`src/database/postgres_handler.py`) — psycopg2 wrapper, `autocommit=True`.
Methods: `fetch_df()`, `fetch_query()`, `upsert_many()`. Initial schema: `init_db.sql`.

### Critical Constants
`ARTIST_NAME_FILTER = "1x7xxxxxxx"` (`src/dashboard/app.py`) — filters the "Total" summary row from S4A CSVs.
**Mandatory**: every query on `s4a_song_timeline` must add `AND song NOT ILIKE '%1x7xxxxxxx%'`.

## Key Commands

### Infrastructure
```bash
docker-compose up -d                              # Start all services
docker-compose build && docker-compose up -d     # Rebuild after requirements.txt / src/ changes
docker-compose logs -f airflow-scheduler          # Tail scheduler logs
```

### Dashboard / Tests / Debug
```bash
cd src/dashboard && streamlit run app.py          # Dashboard en LOCAL (port 8501)
# (en conteneur : `python3 -m src.dashboard.serve`, qui démarre les métriques AVANT)
# ⚠️ JAMAIS `pytest tests/` à la main — la forme nue perd les drapeaux du Makefile :
make test-changed   # Boucle de code : SEULS les tests atteignables depuis le diff (règle 16) — verdict dans .pytest-last.log
make test-fast      # Avant de commiter : tout sauf les tests de documents
make test           # La barrière avant de livrer — mêmes drapeaux que la CI
make test-docs      # Après avoir touché un document généré
# Un fichier précis reste direct : .venv/bin/python -m pytest tests/test_x.py -q
```

### Le temps de la suite — ce que chaque cible coûte

Mesuré sur ext4 (`~/streamlytics`) le 2026-09-17 — pour CHOISIR une cible :

| geste | ce qu'il lance | coût |
|---|---|---|
| `make test-changed` | les tests atteignables depuis le diff — un `.md`/`.yml` ne force plus la suite entière (2026-09-25) | **secondes à ~2 min** |
| `make test-fast` | tout sauf les documents | `make test` − ~38 s |
| `make test` | la suite, `-n $$W --dist loadgroup` — `$$W` (shell) calculé APRÈS le verrou lourd (R331) | `.claude/dev-docs/test-suite-timing.json` — écrit par `make test` |
| `python3 -m pytest tests/` **(à éviter)** | la même suite **en SÉRIE** | 1 146 s mesurés sur `/mnt/c` ; non remesuré ici |

Le détail — pourquoi la forme nue perd le parallélisme, le calcul des workers et sa
réserve mémoire, le gain ext4 (R117), ce qui a été refusé — est dans `.claude/dev-docs/claude-md-measures.md` §1.
Une suite tourne-t-elle : `make suite-status` ; où en est-elle : `tail -3 .pytest-last.log`.

### Running Migrations

**WSL / bash / macOS / CI** (preferred): `make migrate` — pipes every `migrations/*.sql`
through `docker exec -i <pg> psql -U postgres -d spotify_etl`, container auto-detected.

**Windows PowerShell** (no `make`, no local `psql`):
```powershell
docker ps --format "table {{.Names}}`t{{.Status}}"     # find the postgres container
Get-Content migrations/<name>.sql | docker exec -i <container> psql -U postgres -d spotify_etl
```

**Never suggest** `psql` as a standalone command, `< file` redirection in PowerShell (not supported), or invoking individual `*.sql` files when `make migrate` would work.

## Configuration

`config/config.yaml` (copy of `config/config.example.yaml`) — dashboard DB credentials + API keys ; the dashboard reads DB config from it **exclusively**.
`.env` / `.env.local` — Docker Compose + python-dotenv ; `.env.local` takes precedence locally.

## Patterns

### Adding a New View
1. Create `src/dashboard/views/<name>.py` with a `show()` function (no arguments).
2. Add `("<label>", "<name>")` to the relevant section in the `_NAV_SECTIONS` constant in `app.py` (sidebar is grouped by section; pick the section matching the user journey). Admin-only pages: also add the key to `_ADMIN_ONLY`.
3. Add routing: `"<name>": "views.<name>"` in `src/dashboard/routes.py`.
→ Full patterns (DB queries, artist filter, role gate): `.claude/skills/dashboard-view/SKILL.md`

### Adding a New DAG
1. Create `airflow/dags/<name>.py` with `sys.path.insert(0, '/opt/airflow')` at top.
2. `default_args`: owner, `depends_on_past=False`, `retries=2`, `retry_delay=timedelta(minutes=10)`.
→ Full patterns (credentials, in-task imports, failure callback): `.claude/skills/airflow-dag/SKILL.md`

## Development tooling

| Topic | File / Command | Notes |
|---|---|---|
| Common commands | `Makefile` | **`make help` is THE list** (~100 targets, by section — R508). Daily ones: `make test-changed`, `make test-verdict` (last suite's verdict), `make suite-status` (is a suite running?), `make ci-wait` (CI of the pushed HEAD), `make test ARGS=tests/x.py` (a subset WITH the workers), `make lint` (= the CI gate), `make psql Q='…'`, `make prod-psql Q='…'` (read-only), `make roadmap-close ID=…`, `make night-status`, `make migrate`, `make deploy`. A retired target fails naming its replacement. |
| Dependencies | `pyproject.toml`, `uv.lock`, `requirements.txt` | Canonical deps + dev extras ; lock via `uv sync --frozen` (`make sync`) ; `requirements.txt` dérivé, kept for the Dockerfile + CI. |
| Lint | `ruff.toml`, ruff 0.15.17 (dev extra, `/home/timothe/.local/bin/ruff`) | CI blocks on `ruff check src/ tests/` since 2026-05-14 (R49 : version remontée avec le lock). |
| Pre-commit + secrets | `.pre-commit-config.yaml` (`make hooks-install`, chained from `make sync`), `.secrets.baseline` | Ruff + secret scan + hygiene on staged files ; a new secret fails the commit — acknowledge via `detect-secrets scan --baseline .secrets.baseline`. |
| Docker context | `.dockerignore` | Strict exclusions (venv/, .claude/, tests/, docs/...) — keeps build context < 50 MB on WSL2. |

## Reference docs (dev-docs/)

When you need depth beyond `CLAUDE.md`, load these on demand :

| File | Content |
|---|---|
| `.claude/dev-docs/architecture.md` | System Mermaid diagram + data flow + table inventory |
| `.claude/dev-docs/roadmap/checklist.md`, `.claude/dev-docs/roadmap/archive.md` | La roadmap — ouvert / livré (§ Roadmap) |
| `docs/adr/ADR-001-*.md`, `docs/adr/ADR-002-*.md`, `docs/adr/ADR-026-*.md` | Roadmap multi-fichiers ; patterns msdr rejetés (son §4 observability est **superseded par ADR-026**) ; Prometheus + Grafana pour SURVEILLER les déclencheurs d'ADR-002/007/014 |
| `docs/checklists_ml/RELEVANT_FOR_STREAMLYTICS.md` | ML checklist sections applicable here |
| `.claude/dev-docs/refactor-audit-dashboard.md`, `.claude/dev-docs/refactor-audit-mlops.md`, `.claude/dev-docs/refactor-audit-2026-08.md` | Audits de refactor : dashboard, MLOps, et celui du 2026-08-20 commandé après les deux tests artiste ratés |
| `.claude/dev-docs/meta-ads-credential-guide.md`, `.claude/dev-docs/soundcloud-oauth-guide.md`, `.claude/dev-docs/token-management-bilan.md` | Jetons : Meta/Instagram (refresh), SoundCloud (mint du refresh_token), matrice multi-plateformes + critère « aucun geste manuel » |
| `.claude/dev-docs/runbook-actions-utilisateur.md` | **Les gestes humains**, un par section, chacun avec la commande qui prouve qu'il est fait. Une section barrée = clos ; `tests/test_roadmap_index_is_honest.py` échoue si une section vivante n'a plus de tâche ouverte |
| `.claude/dev-docs/runbook-artist-test-session.md` | Inviter un artiste à tester — écrit après deux sessions ratées. **C'est la procédure de R1**, la seule tâche encore ouverte |
| `.claude/dev-docs/coverage-themes.md` | Couverture thématique de l'app adossée au corpus `knowledge-rag`, chaque ligne avec livre + page |
| `.claude/dev-docs/prod-health-monitoring.md` | Les 3 surfaces du contrôle de santé quotidien et pourquoi chacune vit où elle vit |
| **Générés, non versionnés (R345, ADR-031)** | `gold-coverage.md` (`make gold-coverage` — carte de la couche or ; sa dernière section = prochaines divergences) ; `error-class-health.md` (`make error-health` — santé du catalogue mesurée depuis git ; `make error-health-check` en CI) ; `error-class-families.md` (`make error-families` — LA question de chaque famille, à lire AVANT d'écrire une classe) ; `.claude/dev-docs/error-inbox.md` (`make error-inbox` — une ligne par empreinte ; fermer : `make error-resolve FP=… NOTE="…"`) |
| `.claude/dev-docs/roadmap/night-run.md` | **Protocole d'une séance longue** — à lire EN PREMIER à chaque réveil (règle 15bis) ; `make night-status` |
| `.claude/dev-docs/claude-md-measures.md` | Les mesures datées et passages détaillés sortis de ce fichier (R631) — les `§n` cités ici |
| `.claude/dev-docs/error-family-rules.md` | **Les 18 règles** — une par famille d'erreurs, chacune avec sa question et l'endroit où elle est attrapée : au **commit** (pytest qui lit le CODE) ou la **nuit** (sonde qui lit le MONDE : prod, CI, secrets). À lire AVANT d'écrire une classe : une classe neuve entre comme instance d'une famille |
| `.claude/dev-docs/studies/2026-10-12-mods-claude-code.md`, `.claude/dev-docs/studies/2026-10-10-outillage-et-lecteurs.md` | Études : mods de Claude Code M1–M6 (revue 2026-10-26, `make reopen-check`) ; outillage E1–E6, verdict + déclencheur de réouverture |
| `.claude/dev-docs/product-backlog.md` | Ce qui attend un **déclencheur produit** (des artistes à interroger, un lancement) — sorti de la roadmap le 2026-09-26 : R148, R163. Quand le déclencheur arrive, la tâche repart dans la roadmap |
| `.claude/dev-docs/ops-mail-journal.md` | Les mails automatiques de streaMLytics (seuls ceux de `noreply@streamlytics.fr`), triés à chaque début de séance : réel / attendu / fausse alerte / test. `make night-status` dit quand il est périmé |
| `.claude/dev-docs/test-suite-performance.md` | **La référence chiffrée de la suite** : ce que coûte chaque poste, les trois chiffres que j'ai eus faux et pourquoi, et ce qui a été écarté avec sa mesure. À lire AVANT toute séance d'optimisation de tests ou de CI — et avant d'annoncer un gain. La suite varie de ±40 % : un écart plus petit n'est pas un résultat |
| `.claude/dev-docs/grafana-correspondence.md` | **La condition bloquante de R115 étape 6** : ce que chaque vue de surveillance montrait, et où c'est dans Grafana. Il CONTREDIT la moitié du plan — trois des quatre vues ne font pas doublon, et le dire est le point. Porte aussi le seul chiffre délibérément abandonné (le « DB ping ») avec son déclencheur de réouverture, et le geste qui reste avant toute suppression |
| `archive/` | **L'archive unique (R305)** : tout ce qui est retiré, une ligne par fichier dans `archive/README.md` (ancien chemin, raison). Rien de vivant n'y lit. La doc de compréhension se régénère à la demande : **`make inventory`** → `revue/inventaire.md` |
| `.claude/dev-docs/architecture/` | **Le référentiel d'architecture (R257)** : `domains.yaml` (24 domaines micro, fichiers vérifiés), `requirements.yaml` (exigences avec source et PREUVE ciblée), `notes-triage.yaml` (chaque note du propriétaire → statut + ligne de roadmap), `benchmark.md` **à la demande** par `make arch-benchmark`, non versionné (R279) |

The graph at `graphify-out/GRAPH_REPORT.md` (auto-regenerated by `graphify update .`) is the **fastest way** to discover what's connected to what — read it before grepping.

## .claude/ Tooling

### Cross-Cutting Rules (always active — no file read needed)

Full specification: `.claude/skills/response-protocol/SKILL.md` (load only for `/review-*` commands).

1. **Language**: English in all code, comments, docstrings, docs. Exception: Streamlit UI strings.
2. **Neutrality**: Cold technical feedback. State behavior + consequence. Enumerate ≥2 alternatives with trade-offs before recommending.
3. **Classification**: Label every new file in its docstring: `Type: Core|Feature|Sub|Hook|Utility` + `Uses/Triggers/Depends on/Persists in`.
4. **Priority**: P1 (crash/security) > P2 (data integrity) > P3 (UX) > P4 (tech debt). Never address P4 during a P1 session.
5. **Retirée le 2026-09-25** — elle nommait un agent de documentation d'arrière-plan sous la forme d'une RESTRICTION (« only after ≥3 files »), sans flèche ni évènement : **0 appel sur 51 sessions** (`usage_report.py`). Ses quatre devoirs ont un propriétaire vivant : DEVLOG → archivé (R311, la trace d'une livraison est `make roadmap-close`) ; roadmap → `roadmap-keeper` (règle 17) ; REX → `draft_rex.py` + `/retro` ; Mermaid → `code-architecture-reviewer` (règle 18). Le numéro est gardé pour ne pas renuméroter 12-21. Pourquoi : `archive/claude-config/agents/POURQUOI-STRATEGIC-PLAN-ARCHITECT.md`. Garde : `tests/test_claude_config_floor.py::test_every_declared_agent_has_a_trigger_that_can_fire`.
6. **Collectors must raise**: `except Exception` blocks in `src/collectors/` must always `raise` — never `return None`, `return []`, or `break` silently. Any deviation is a P2 data-integrity bug. A commit touching `src/collectors/` runs the pre-commit hook `collector-audit` (R1 raise + R4 tenant-named writes, blocking); `/audit-collectors` stays a manual review for R2/R3 (R472 — suggested by prose, it ran 0 times in 44 sessions).
7. **`get_artist_id()` guard**: Never write `get_artist_id() or 1`. New views MUST use the `view_session()` context manager (`src/dashboard/utils/__init__.py`) which encapsulates the guard — `with view_session() as (db, artist_id): ...`. The manual guard below is the legacy form (still valid in not-yet-migrated views):
   ```python
   artist_id = get_artist_id()
   if artist_id is None:
       if not is_admin(): st.error("Session invalide."); st.stop()
       artist_id = 1  # admin fallback — document explicitly
   ```
8. **SQL identifier allowlists**: Any f-string that interpolates a table name or column name must validate against a `frozenset` allowlist before execution. Values (user data) always use `%s` parameterization — never f-strings.
9. **DB connections per request**: `get_artist_plan()` uses 1 single LEFT JOIN query. Views open exactly 1 connection via `view_session()` (auto-closed on exit) — never open `db2` as a fallback inside the same function. `view_session()` enforces this structurally.
10. **Makefile fail-fast**: any target invoking a runtime dependency (Docker, the venv interpreter, the live Postgres, `uv`, `streamlit`) must declare a prerequisite that fails fast with an actionable message — the `dashboard: check-env` precedent. File-only targets (`clean`, `help`, `graph-html`) are exempt. A runtime target with no precondition is a P3 bug: it must name the fix command, never crash mid-execution. Error class: `make-fail-late` (`.claude/dev-docs/error-classes.md`); full spec `.claude/rules/makefile-fail-fast.md`.
11. **Bug → whole-repo impact analysis**: the moment a bug, divergence, regression, drift, or 500/crash is identified, load `.claude/skills/impact-analysis/SKILL.md` and follow it **before** writing the fix. A defect is an instance of a *class* — sweep the whole repo for sibling occurrences (the proven `/kpis` → `/youtube` drift lesson), root-cause by reading the code (not guessing), and ship fix **+ a durable guard** (error-class signature / test / hook) so the class can't recur. ⚠️ The skill itself is NOT injected (no `keywords:` — it said so until 2026-09-25, falsely): what `inject_context.py` injects on ≥2 bug-keywords is `bug-resolution.md`, whose step 2 is `Spawn sibling-sweeper`, and a commit that writes a class or a `(récidive)` line without a real sweeper call in the project's transcripts is blocked by `.claude/hooks/require_sweep_before_catalogue.py`. If prod-affecting, finish with `make sync-check`. The sequenced version of this rule is `.claude/workflows/bug-resolution.md`, injected on the same keywords — **run it, do not wait to be asked.**

12. **≥5 tests rouges dans une même exécution → `Spawn build-error-resolver`.** Il renvoie **la cause
    racine unique**, le fichier et la ligne où elle se lit, **la chaîne qui y mène** — le symptôme, puis
    chaque « pourquoi » jusqu'à une cause qu'on peut supprimer — et la liste **de tous les sites** qu'elle
    touche, y compris ceux qu'aucun test n'exerce ; il ne réécrit aucun code non lié (contrat v3 du
    baseline : la vraie cause nommée passe de 43 % à 77 %). Seuil = `failures >= 5` de
    `session_summary.py` (le baseline v3 dit ≥1) : le changer, c'est éditer ensemble la règle, l'agent et le hook.

13. **Un endpoint HTTP, une route d'authentification ou une lecture de secret ajoutée ou modifiée → `Spawn security-specialist`.** Il renvoie des constats CRITICAL/HIGH/MEDIUM avec fichier et ligne.

> Règles 12-13 (2026-07-28) : une flèche, un déclencheur vérifiable, le verbe littéral
> `Spawn`, un contrat de sortie — le seul mécanisme mesuré qui produise des invocations (§7).

<!-- measured-rules:begin v3 — tools/dev/install_measured_rules.py (le baseline ; règle « cause » portée par la 12, hors bloc) -->

14. **Une classe de défaut identifiée → `Spawn sibling-sweeper` AVANT d'écrire le
    fix.** Il renvoie la liste exhaustive des sites frères en `fichier:ligne`, en
    balayant le code, les tests **et** la couche de configuration. Un correctif
    qui ne balaie pas laisse la classe vivante ailleurs.
    **Un constat de sécurité (gitleaks, secret exposé, CVE) EST une classe de défaut** (§2bis) ;
    surfaces publiques balayées chaque nuit par `tools/dev/sweep_public_surfaces.py`.

15. **Un défaut corrigé → un TEST. Une CLASSE seulement avec un billet
    d'admission → `/capitalise`.** Depuis le 2026-09-19, une classe neuve porte
    `- admitted:` avec un NOMBRE, jamais un jugement : `recurrence:<date1>,<date2>`
    (daté deux fois — une fois est un accident), `sites:<N≥2>` (un balayage a trouvé au
    moins deux sites vivants), ou `p1:<impact production nommé>`. Si aucun des trois ne
    tient, on écrit le test et on le dit (pourquoi ce billet, et pourquoi 2 sites : §2).
    Contrôle bloquant : `python3 .claude/scripts/audit_runner.py --admission`.
    Une fois le billet acquis, `/capitalise` écrit l'entrée. Elle renvoie l'entrée pour
    `.claude/dev-docs/error-classes.md` au schéma du fichier, dont un
    `root_cause`, un `long_term_fix` — le changement qui rend la classe
    impossible — et une `signature` shell **qu'elle a vue sortir ≠ 0 sur le
    défaut** et 0 après le fix. Une signature jamais vue rouge ne garde rien.
    L'entrée porte **trois preuves**, chacune née d'un échec mesuré : `seen_red:` (la
    date où la signature est sortie ≠ 0, ou `never`/`n-a` — **jamais une date non
    observée**), `cause_evidence:` (`read`/`measured`/`inferred`/`retracted` — une cause
    plausible s'écrit `inferred`, pas dans la voix d'un fait), et `guard_scope:` (la
    **famille de geste** couverte, et au moins un geste voisin **non couvert**).
    **Aucune règle ne cite un chiffre de récidive comme sa preuve** : découpée au premier
    garde (sans biais d'*immortal time*), la récidive ne change pas (×1,1). Une ligne
    d'`History` déclare sa nature — `- AAAA-MM-JJ (récidive):` ou `(garde):` — et seule la
    première compte. Mesures et pari `seen_red` : `claude-md-measures.md` §2. Contrôles :
    `tests/test_the_guard_axis_is_measured_without_immortal_time.py`,
    `tests/test_the_error_class_health_only_improves.py`, `make error-health`.

15bis. **Séance longue sans interlocuteur — `/loop`, une consigne de nuit, ou plus de
    deux heures sans retour humain → lire `.claude/dev-docs/roadmap/night-run.md` et
    lancer `make night-status` AVANT toute autre chose.** Puis une unité à la fois :
    `night-start` → le travail → `make test-changed` → commit poussé → `night-done`.
    Bloqué ⇒ `make night-park` et la tâche suivante ; **on ne s'arrête jamais sur un
    blocage**, il consommerait toutes les heures restantes.
    Pourquoi (le contexte est compacté, la roadmap ne dit pas *où j'en étais*) : §3.
    Contrôle : `make night-check` — arbre sale, commits non poussés, unité ouverte
    depuis plus de 3 h.

15ter. **Muter un garde neuf AVANT de le croire → `python3 tools/dev/mutate_guards.py
    <tests/test_x.py>`.** Il propose une mutation, l'applique, lance le garde, et
    RESTAURE l'arbre quoi qu'il arrive. Un garde jamais vu rouge ne garde rien, et la
    seule façon de le savoir est de le mettre en défaut. Il ne DATE rien : un humain
    décide si la mutation INCARNE le défaut, et vérifie que la ligne a CHANGÉ (§4).
    Contrôle que l'outil reste atteignable : `make config-check`.

16. **Avant de lancer la suite après un changement de code → lancer
    `python3 .claude/scripts/select_tests.py`.** Il rend les tests atteignables
    depuis ce qui a changé — ou la suite entière quand il ne peut pas conclure.
    Lancer cette liste, pas la suite entière.

17. **Une tâche livrée → `make roadmap-close ID=Rnnn NOTE="…"`** (R199, 2026-09-26) : elle
    écrit l'entrée d'archive en tête — texte de la ligne, mesure, commits qui la LIVRENT
    (un commit roadmap seul ne livre rien) — retire la ligne et recale l'ancre ; une
    seconde fermeture échoue. **Un LOT de briques, ou une brique abandonnée dont il faut
    raconter la leçon → `Spawn roadmap-keeper`.** Il renvoie les deux fichiers (§ Roadmap)
    mis à jour — retirée de l'actif **et** ajoutée à l'archive, jamais l'un sans l'autre,
    ligne d'index retirée, aucune statistique inventée. Contrôle :
    `tests/test_roadmap_two_files.py` échoue si la somme des deux fichiers rétrécit.

18. **≥5 modules ajoutés, supprimés ou renommés sous `src/` dans une session, ou un diagramme de
    `.claude/dev-docs/architecture.md` touché → `Spawn code-architecture-reviewer`.** Il renvoie un
    tableau `| Diagramme | Constat | Sévérité | Action |` de dérive **factuelle**, jamais de style.
    Déclencheur : `git diff --name-status <base>..HEAD -- src/ | grep -cE '^(A|D|R)'`.

19. **Un comportement d'API externe qu'aucun fichier de `.claude/dev-docs/` ne documente — code
    d'erreur inconnu, champ disparu, intégration qui cesse sans changement de notre côté → `Spawn
    web-research-specialist`.** Il renvoie ≤500 mots (l'API, ses contraintes, ce qui s'applique, les
    liens, deux sources qui se contredisent). Déclencheur : `grep -rl "<code>" .claude/dev-docs/` vide.

20. **Un balayage qui publie un NOMBRE de sites → le muter dans les DEUX SENS avant de
    l'écrire.** Un **faux positif** (un site qui a la forme et n'est PAS le défaut) et un
    **faux négatif** (un site qui EST le défaut, écrit autrement). Et le champ `siblings:`
    porte l'entonnoir minimal qui rende le chiffre contredisable : candidats bruts →
    écartés avec leur raison → sites vivants.
    Pourquoi — dix prédicats faux au premier jet, toujours en sur-comptant : §5.
    Classe : `a-sweep-predicate-that-matches-a-form-not-a-property`.
    Contrôle : `make error-health` → panneau « Ce que le balayage RAPPORTE » ; un balayage
    dont le verdict n'est pas lisible compte dans `sites_unknown`, un trou sous cliquet.

21. **Balayer par FAMILLE, pas par classe.** Les classes d'une même famille partagent
    leur cause, donc une seule mesure en tranche plusieurs.
    Mesure (99 % puis 94 % des classes balayées l'ont été avec leur famille) : §6.
    `error-class-families.md` (dev-docs/) porte, pour chaque famille, LA question.

22. **Toucher un domaine → lire sa fiche dans `.claude/dev-docs/architecture/domains.yaml`
    et ses exigences dans `requirements.yaml` AVANT d'écrire.** Une exigence nouvelle (une
    propriété durable : modularité, un seul calcul, mêmes filtres…) entre au catalogue avec
    sa source et UNE preuve rejouable ciblée sur une ligne — ou un `a_ecrire`, compté comme
    trou. Contrôle : `tests/test_every_requirement_has_a_probe.py` (toute preuve se résout) ;
    `tests/test_every_note_is_on_the_roadmap.py` (toute note du propriétaire encore à faire
    nomme une ligne réelle). Mesure : `make arch-benchmark`.

23. **Un design de correctif à juger HORS de la boucle d'ingénierie — une trouvaille seule qui touche
    un garde, un installeur ou une frontière irréversible, ou un refactor de plus de 3 fichiers →
    `Spawn code-critic` sur le DESIGN, avant la première ligne.** Il rend `BUILD`, `BUILD-MODIFIED`
    ou `DO-NOT-BUILD`, avec la raison ; dans la boucle, c'est elle qui le lance (phase Critic).
    Source : `agent-triggers` du master (T148) — R651.

> Règles 18-19 (2026-08-21) : ces agents n'étaient nommés que dans un tableau (§7bis).

<!-- measured-rules:end v3 -->
### Skills (`.claude/skills/<nom>/SKILL.md`) — load on demand via Skill tool only

Each skill is a **directory** (`.claude/skills/impact-analysis/SKILL.md`), never a flat `<nom>.md`.

| Skill | Use when |
|---|---|
| `dashboard-view/` | Implementing a new Streamlit view from scratch |
| `airflow-dag/` | Creating a new DAG |
| `db-schema/` | Designing a new table or migration |
| `response-protocol/` | Detailed audit rules — `disable-model-invocation: true`, so **manual only** (`/review-*`) |
| `audit-collectors/` | Silent success anti-pattern rules — load when touching collectors |
| `impact-analysis/` | A bug/divergence/drift/500 was identified — whole-repo impact sweep + root-cause + durable guard (rule #11) |
| `continuous-learning/` | Capturer un motif non évident trouvé en séance — **manuelle** depuis R417 (2026-10-06) : le rappel de fin de tour et le hook `observe.py` qui l'alimentaient sont archivés, 48 séances, 0 appel |

⚠️ **Deux skills retirées le 2026-09-18** (`systematic-debugging/`, `verification/`), vers `archive/claude-config/skills/` — couvertes par `workflows/bug-resolution.md`. La loi mesurée de ce dépôt vaut aussi pour les skills : **ce qui n'est nommé nulle part n'est jamais invoqué.** Réouverture : `archive/claude-config/skills/POURQUOI-CES-DEUX.md`.

### Workflows (`.claude/workflows/`) — playbooks the model EXECUTES

Auto-injected by `inject_context.py` via their `keywords:` frontmatter — **run it; do not wait to be asked.**

| Playbook | Auto-loads on |
|---|---|
| `bug-resolution.md` | bug / régression / traceback / corruption / silent failure / test rouge |
| `architecture-change.md` | ADR / migration / schéma / contrat / breaking change |
| `feature-development.md` | nouvelle fonctionnalité / brique / endpoint |
| `continuous-improvement.md` | améliorer la config / curator / agent roster / dette technique |
| `architecture-requirements.md` | modularité / scalabilité / exigence / domaine / « même filtre » / « une seule définition » |

### Agents, slash commands, mise en route MCP, RTK

Documentation, pas déclencheurs : `.claude/dev-docs/tooling-reference.md`. Les agents invoqués le sont
par les règles 12, 13, 14, 17, 18, 19 et la boucle d'ingénierie (`code-critic`) — pas par un tableau.

### Hooks
- **UserPromptSubmit** → `inject_context.py` — keyword-triggered skill injection (domain patterns)
- **PreToolUse (Bash)** → `guard_destructive.py` — gestes irréversibles, gardes à ÉTAT : un
  rétablissement git sur du travail non commité, un `kill` par motif suivi d'autre chose (§8).
- **PreToolUse (Edit|Write|…)** → `require_roadmap_entry.py` — pas de code produit sans ligne ouverte (R196).
- **PostToolUse** → `check_python_syntax.py` — ruff (E9 bloque) ; avertit si une suite complète tourne.
- **Stop** → `session_summary.py` (git diff, Docker health, symptômes → `make defect-log`) ; `require_verdict_after_edit.py`
  (R549 — code modifié après le départ de la dernière suite ⇒ fin de tour bloquée UNE fois ; un `.md` seul non).
  `roadmap_empty_beep.py` (baseline `governance`, 2026-10-16) — un bip quand la roadmap passe à 0 tâche,
  jamais entre 01:00 et 09:20 ; `ROADMAP_BEEP=0` le coupe.
- **statusLine** → `.claude/scripts/statusline.py` (R550) — HUD : tests, CI du HEAD (« ? » si non lue).
→ Full specification: `.claude/hooks/hook.md`

> Pourquoi des hooks plutôt que des règles, et pourquoi un garde de Bash lit la STRUCTURE
> de la commande et pas sa prose : §8. Contrôle : `tests/test_a_bash_guard_reads_the_command_not_the_prose.py`.

## MCP Servers

All MCPs are declared at project level in `.mcp.json` — **gitignored, local-only**. Each developer maintains their own copy; credentials are resolved at runtime via `${VAR}` from your shell environment or `.env.local`. If you onboard a teammate, share the config out-of-band (1Password, secure channel) — never commit it.

| MCP | Purpose | Required env var |
|---|---|---|
| `graphify` | Local code knowledge graph (1500+ nodes) | — |
| `spotify-postgres` | Direct SQL on `spotify_etl` (read-only) | `DB_PASSWORD` |
| `github` | PR / Actions / issues review | `GITHUB_TOKEN` |
| `chrome-devtools` | Streamlit UI inspection (console, Lighthouse) | — (Chromium installed in WSL2) |
| `airflow` | DAG inspection via REST API (read-only) | `AIRFLOW_ADMIN_USERNAME`, `AIRFLOW_ADMIN_PASSWORD` |

## Roadmap

**Deux fichiers, un seul actif** : `.claude/dev-docs/roadmap/checklist.md` (ouvert, état de
reprise — lu par `/resume`, `/sprint`) et `.claude/dev-docs/roadmap/archive.md` (livré, passif).
Resume after `/clear`: *"Read `.claude/dev-docs/roadmap/checklist.md` and continue with the next unchecked item."*

**Une action entre dans la roadmap AVANT d'être exécutée — gardé, pas conseillé (R196).**
(1) ligne `| Rnnn | … |` dans l'index + commit « Roadmap : Rnnn inscrite » ; (2) le code,
commité « Rnnn : … » ; (3) `make roadmap-close`. Barrières : `require_roadmap_entry.py`
(PreToolUse), `tools/dev/require_roadmap_id.py` (commit-msg), job CI `roadmap` (§9).

**Roadmap flow**: `## 📋 Tâches ouvertes` indexes only still-open tasks. Done → `make roadmap-close
ID=<id> NOTE="…"` (or `/roadmap-done`); a batch → règle 17. Never hand-delete an item.
Briques 1–17 (fondations SaaS) : toutes livrées — table historique en §9bis.

## Tooling auxiliaire
### Graphify — local knowledge graph
Indexed code graph in `graphify-out/` (**gitignored**), queried by the `graphify` MCP. Refresh
after ≥ 5 files changed: `make graph` (= `make graph-update` + `make graph-html`).
Avant d'agir sur un chemin lu dans `GRAPH_REPORT.md`, vérifier qu'il existe : `graphify
update` ajoute et ne retire pas — le graphe oriente, il ne prouve pas. Vue visuelle :
`graphify-out/graph.html` (autonome, `make graph-html`). Tailles et résidu mesurés : §10.

<!-- baseline-pointer v6 — source unique : tools/dev/claude-md-pointer.md du baseline.
     Ne pas éditer ici : éditer la source et relancer install_conformance_ratchet.py --write.
     Tout ce qui est entre ce marqueur et son marqueur de fin est REMPLACÉ à chaque
     déploiement. Le reste de ce CLAUDE.md n'est jamais touché. Les `args` sont rendus
     avec les valeurs de CE dépôt (governance.toml, section [loop]). -->

## Règle contraignante — la boucle d'ingénierie

**≥2 trouvailles dans une même séance → `RUN Workflow({name: "engineering-loop", args: {findings: [une chaîne par trouvaille], roadmap: ".claude/dev-docs/roadmap/checklist.md", prefix: "R", method: ".claude/skills/impact-analysis/SKILL.md", catalogue: ".claude/dev-docs/error-classes.md", critic_agent: "code-critic"}})`**, pas une correction à la main trouvaille par trouvaille.

`.claude/workflows/engineering-loop.js` enchaîne quatre phases : **Impact** (un agent par
trouvaille — cause racine lue dans le code, puis balayage des frères sur tout le dépôt)
→ **Critic** (`code-critic` sur le DESIGN du fix, *avant* qu'une ligne soit écrite :
`BUILD` / `BUILD-MODIFIED` / `DO-NOT-BUILD`) → **Fix** (les approuvés seulement, en
worktree isolé, avec garde et mutation ciblée) → **Improve** (critique de complétude).

Il retourne un **manifeste de déploiement** : il n'écrit jamais la ROADMAP et ne commite
jamais. Le déploiement se fait depuis le contexte principal, ROADMAP d'abord.

Une trouvaille isolée ne le justifie pas — le workflow ne se rentabilise que sur un lot.

⚠️ Cette ligne est une **règle**, pas une note de playbook, pour une raison mesurée :
un agent nommé dans une règle impérative est invoqué ; nommé dans une étape d'un playbook
injecté 98 fois, il ne l'a **jamais** été — 0 spawn sur les 5 concernés. Un fichier
présent que rien ne nomme ne tourne pas.

<!-- /baseline-pointer -->
