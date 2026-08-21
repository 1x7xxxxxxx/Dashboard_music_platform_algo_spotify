# CLAUDE.md

## Project Overview

**streaMLytics** — Multi-tenant music analytics SaaS. ELT pipeline: external APIs and CSVs → Airflow DAGs (Docker) → PostgreSQL `spotify_etl` → Streamlit dashboard. Sources: Spotify API, Spotify for Artists CSV, Meta Ads, YouTube, SoundCloud, Instagram, Apple Music.

## Architecture

### Data Flow
```
External APIs / CSV files
        ↓
Airflow DAGs (Docker containers)
        ↓
PostgreSQL `spotify_etl` DB (port 5433 locally)
        ↓
Streamlit Dashboard (local, port 8501)
```

### Docker Services
- **postgres** — PostgreSQL 17, port 5433→5432. Databases: `airflow_db` (Airflow metadata), `spotify_etl` (app data)
- **airflow-webserver** — port 8080, UI at http://localhost:8080
- **airflow-scheduler** — auto-picks up `airflow/dags/`
- **airflow-init** — one-shot DB init + admin user creation

`src/` and `airflow/dags/` are volume-mounted into containers — changes go live without rebuild.

### Source Layout
```
src/
  collectors/   # API clients (spotify, youtube, soundcloud, instagram, meta, s4a)
  transformers/ # CSV parsers (s4a, apple_music, meta_csv, meta_insight)
  database/     # PostgresHandler + per-platform schema definitions
  models/       # Pydantic validators (meta_ads_validators)
  utils/        # config_loader, airflow_trigger, email_alerts, error_handler, retry
  dashboard/
    app.py      # Streamlit entry point + routing
    views/      # One file per page
    utils/      # get_db_connection, airflow_monitor

airflow/
  dags/         # Production DAGs (live-mounted)
  debug_dag/    # Standalone debug scripts (one per DAG)
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
cd src/dashboard && streamlit run app.py          # Run dashboard (local, port 8501)
python3 -m pytest tests/ -v                       # Run unit tests
python airflow/debug_dag/debug_<name>.py          # Run a DAG locally without Airflow
```

### Running Migrations

Two equivalent paths — pick by the shell you're in :

**From WSL / bash / macOS / CI** (preferred — single command, idempotent across all `migrations/*.sql`) :
```bash
make migrate
```
This iterates over `migrations/*.sql` and pipes each through `docker exec -i <pg> psql -U postgres -d spotify_etl`. Auto-detects the running postgres container.

**From Windows PowerShell** (when `make` isn't available; `psql` isn't installed locally either) :
```powershell
# Step 1 — find the postgres container name
docker ps --format "table {{.Names}}`t{{.Status}}"

# Step 2 — run a single migration (replace <container> with the actual name)
Get-Content migrations/<name>.sql | docker exec -i <container> psql -U postgres -d spotify_etl
```

**Never suggest** `psql` as a standalone command, `< file` redirection in PowerShell (not supported), or invoking individual `*.sql` files when `make migrate` would work.

## Configuration

Two mechanisms coexist:
1. `config/config.yaml` — dashboard DB credentials + API keys. Copy from `config/config.example.yaml`.
2. `.env` / `.env.local` — Docker Compose + python-dotenv. `.env.local` takes precedence locally.

Dashboard reads DB config from `config/config.yaml` exclusively (not `.env`).

## Patterns

### Adding a New View
1. Create `src/dashboard/views/<name>.py` with a `show()` function (no arguments).
2. Add `("<label>", "<name>")` to the relevant section in the `_NAV_SECTIONS` constant in `app.py` (sidebar is grouped by section; pick the section matching the user journey). Admin-only pages: also add the key to `_ADMIN_ONLY`.
3. Add routing: `elif page == "<name>": from views.<name> import show; show()`.
→ Full patterns (DB queries, artist filter, role gate): `.claude/skills/dashboard-view/SKILL.md`

### Adding a New DAG
1. Create `airflow/dags/<name>.py` with `sys.path.insert(0, '/opt/airflow')` at top.
2. Create `airflow/debug_dag/debug_<name>.py` for local testing.
3. `default_args`: owner, `depends_on_past=False`, `retries=2`, `retry_delay=timedelta(minutes=10)`.
→ Full patterns (credentials, in-task imports, failure callback): `.claude/skills/airflow-dag/SKILL.md`

## Development tooling

| Topic | File / Command | Notes |
|---|---|---|
| Common commands | `Makefile` | `make help` lists 11 targets (up/down/logs/test/lint/migrate/dashboard/sync/clean/graph/hooks-install). |
| Dependency manifest | `pyproject.toml` | Canonical project deps + dev extras (pytest, ruff, pre-commit, detect-secrets). |
| Lock file | `uv.lock` | Reproducible installs via `uv sync --frozen` (or `make sync`). |
| Legacy install path | `requirements.txt` | Kept parallel for the existing Dockerfile + CI workflow. Dérivé de `pyproject.toml`. |
| Lint config | `ruff.toml` | Authoritative ruff config. CI blocks on `ruff check src/ tests/` since 2026-05-14. |
| Ruff binary | `pip install ruff==0.15.5` (dev extra) | Available system-wide as `/home/timothe/.local/bin/ruff`. |
| Pre-commit hooks | `.pre-commit-config.yaml` + `make hooks-install` | Ruff + secret scan + hygiene on staged files. Chained from `make sync`. Bypass : `git commit --no-verify`. |
| Secret baseline | `.secrets.baseline` | Versioned acknowledged-matches list. New secrets fail commit; update baseline via `detect-secrets scan --baseline .secrets.baseline`. |
| Docker context | `.dockerignore` | Strict exclusions (venv/, .claude/, tests/, docs/...) — keeps build context < 50 MB on WSL2. |

## Reference docs (dev-docs/)

When you need depth beyond `CLAUDE.md`, load these on demand :

| File | Content |
|---|---|
| `.claude/dev-docs/architecture.md` | System Mermaid diagram + data flow + table inventory |
| `.claude/dev-docs/roadmap/checklist.md` | Live brick tracker — **open work only** |
| `.claude/dev-docs/roadmap/archive.md` | Delivered bricks + closed bugs (passive) |
| `docs/adr/ADR-001-*.md` | Roadmap-multi-files-conserved decision |
| `docs/adr/ADR-002-*.md` | Rejected msdr patterns (Alembic, repo pattern, observability) |
| `docs/checklists_ml/RELEVANT_FOR_STREAMLYTICS.md` | ML checklist sections applicable here |
| `.claude/dev-docs/refactor-audit-dashboard.md` | Prioritized dashboard refactor pain points |
| `.claude/dev-docs/refactor-audit-mlops.md` | MLOps audit + scope decisions |
| `.claude/dev-docs/meta-ads-credential-guide.md` | Meta/Instagram token setup + refresh behavior |
| `.claude/dev-docs/soundcloud-oauth-guide.md` | SoundCloud OAuth refresh_token mint runbook (real likes) |
| `.claude/dev-docs/token-management-bilan.md` | Cross-platform token/refresh matrix + admin/end-user no-manual-action criterion |

The graph at `graphify-out/GRAPH_REPORT.md` (auto-regenerated by `graphify update .`) is the **fastest way** to discover what's connected to what — read it before grepping.

## .claude/ Tooling

### Cross-Cutting Rules (always active — no file read needed)

Full specification: `.claude/skills/response-protocol/SKILL.md` (load only for `/review-*` commands).

1. **Language**: English in all code, comments, docstrings, docs. Exception: Streamlit UI strings.
2. **Neutrality**: Cold technical feedback. State behavior + consequence. Enumerate ≥2 alternatives with trade-offs before recommending.
3. **Classification**: Label every new file in its docstring: `Type: Core|Feature|Sub|Hook|Utility` + `Uses/Triggers/Depends on/Persists in`.
4. **Priority**: P1 (crash/security) > P2 (data integrity) > P3 (UX) > P4 (tech debt). Never address P4 during a P1 session.
5. **Background agent**: Spawn `strategic-plan-architect` only after ≥3 files changed in one session. Not after single-file edits.
6. **Collectors must raise**: `except Exception` blocks in `src/collectors/` must always `raise` — never `return None`, `return []`, or `break` silently. Any deviation is a P2 data-integrity bug. Run `/audit-collectors` after touching any collector.
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
11. **Bug → whole-repo impact analysis**: the moment a bug, divergence, regression, drift, or 500/crash is identified, load `.claude/skills/impact-analysis/SKILL.md` and follow it **before** writing the fix. A defect is an instance of a *class* — sweep the whole repo for sibling occurrences (the proven `/kpis` → `/youtube` drift lesson), root-cause by reading the code (not guessing), and ship fix **+ a durable guard** (error-class signature / test / hook) so the class can't recur. The skill is auto-injected by `inject_context.py` on ≥2 bug-keywords; this rule makes it mandatory regardless. If prod-affecting, finish with `make sync-check`. The sequenced version of this rule is `.claude/workflows/bug-resolution.md`, injected on the same keywords — **run it, do not wait to be asked.**

12. **≥5 tests rouges dans une même exécution → `Spawn build-error-resolver`.** Il renvoie
    la chaîne causale jusqu'à une cause **qu'on peut retirer**, les sites qu'elle touche, et
    le fix minimal — sans toucher au code non lié. Le seuil est celui que `session_summary.py`
    signale réellement (`failures >= 5`) : le changer suppose d'éditer les trois surfaces
    ensemble — cette règle, la description de l'agent, et le hook.

13. **Un endpoint HTTP, une route d'authentification ou une lecture de secret ajoutée ou modifiée → `Spawn security-specialist`.** Il renvoie des constats CRITICAL/HIGH/MEDIUM avec fichier et ligne.

> Règles 12-13 ajoutées le 2026-07-28. Forme imposée par `ARCHITECTURE.md` §3.2 du baseline :
> une flèche, un déclencheur **vérifiable mécaniquement**, le verbe littéral `Spawn`, un
> contrat de sortie. C'est le seul mécanisme mesuré qui produise des invocations — 33 spawns
> pour les agents nommés dans une règle impérative, **0 sur 23** pour ceux nommés dans un
> tableau ou un registre. Les tableaux d'agents ci-dessous sont de la documentation, pas un
> déclencheur.

<!-- measured-rules:begin v2 — tools/dev/install_measured_rules.py -->

14. **Une classe de défaut identifiée → `Spawn sibling-sweeper` AVANT d'écrire le
    fix.** Il renvoie la liste exhaustive des sites frères en `fichier:ligne`, en
    balayant le code, les tests **et** la couche de configuration. Un correctif
    qui ne balaie pas laisse la classe vivante ailleurs.

15. **Un défaut corrigé → `/capitalise`.** Elle renvoie l'entrée pour
    `.claude/dev-docs/error-classes.md` au schéma du fichier, dont un
    `root_cause`, un `long_term_fix` — le changement qui rend la classe
    impossible — et une `signature` shell **qu'elle a vue sortir ≠ 0 sur le
    défaut** et 0 après le fix. Une signature jamais vue rouge ne garde rien.

16. **Avant de lancer la suite après un changement de code → lancer
    `python3 .claude/scripts/select_tests.py`.** Il rend les tests atteignables
    depuis ce qui a changé — ou la suite entière quand il ne peut pas conclure.
    Lancer cette liste, pas la suite entière.

17. **Une brique livrée ou abandonnée → `Spawn roadmap-keeper`.** La ROADMAP est en
    **deux fichiers** : `.claude/dev-docs/roadmap/checklist.md` (actif — ce qui est
    ouvert) et `.claude/dev-docs/roadmap/archive.md` (livré ou clos). Il renvoie les
    deux mis à jour : la brique retirée de l'actif **et** ajoutée à l'archive, jamais
    l'un sans l'autre, plus la ligne d'index `## 📋 Tâches ouvertes` retirée. Ces
    fichiers ne portent aucune statistique agrégée : il n'en invente pas.
    Contrôle : `python3 -m pytest tests/test_roadmap_two_files.py -q` échoue si la
    somme des deux fichiers rétrécit — une rotation qui perd un item améliore le
    pourcentage sans rien livrer.

18. **≥5 modules ajoutés, supprimés ou renommés sous `src/` dans une session, ou un
    diagramme de `.claude/dev-docs/architecture.md` touché → `Spawn
    code-architecture-reviewer`.** Il renvoie un tableau `| Diagramme | Constat |
    Sévérité | Action |` de dérive **factuelle** entre le diagramme et le code, jamais
    de suggestion de style. Déclencheur vérifiable : `git diff --name-status
    <base>..HEAD -- src/ | grep -cE '^(A|D|R)'`. La Views Map a déjà divergé deux fois
    sans que rien ne le signale.

19. **Un comportement d'API externe qu'aucun fichier de `.claude/dev-docs/` ne
    documente — code d'erreur inconnu, champ disparu, intégration qui cesse de
    fonctionner sans changement de notre côté → `Spawn web-research-specialist`.** Il
    renvoie ≤500 mots : ce que fait l'API / ses contraintes / ce qui s'applique ici /
    les liens, et signale explicitement deux sources qui se contredisent. Déclencheur
    vérifiable : `grep -rl "<le code d'erreur>" .claude/dev-docs/` ne renvoie rien.
    Le cas vivant est R13 — Meta répond `code-190` sur tout REST depuis des semaines.

> Règles 18-19 ajoutées le 2026-08-21 pour la raison mesurée ci-dessus, et pas pour
> gonfler un score : ces deux agents n'étaient nommés que dans un tableau, donc jamais
> déclenchés. Si un déclencheur ne se produit jamais en pratique, retirer l'agent est
> la bonne réponse — pas lui inventer une règle.

<!-- measured-rules:end v2 -->
### Skills (`.claude/skills/<nom>/SKILL.md`) — load on demand via Skill tool only

Spec layout: each skill is a **directory**. The flat `<nom>.md` form was migrated away and
every path below was pointing beside the file until 2026-07-28 — a reference that misses
without complaining is the `.claude/skills/impact-analysis/SKILL.md` case of rule #11, which named
a file that had not existed for weeks.

| Skill | Use when |
|---|---|
| `dashboard-view/` | Implementing a new Streamlit view from scratch |
| `airflow-dag/` | Creating a new DAG or debug_dag |
| `db-schema/` | Designing a new table or migration |
| `response-protocol/` | Detailed audit rules — `disable-model-invocation: true`, so **manual only** (`/review-*`) |
| `audit-collectors/` | Silent success anti-pattern rules — load when touching collectors |
| `impact-analysis/` | A bug/divergence/drift/500 was identified — whole-repo impact sweep + root-cause + durable guard (rule #11) |

### Workflows (`.claude/workflows/`) — playbooks the model EXECUTES

Auto-injected by `inject_context.py` via their `keywords:` frontmatter. When one lands in
context, **run it; do not wait to be asked.**

| Playbook | Auto-loads on |
|---|---|
| `bug-resolution.md` | bug / régression / traceback / corruption / silent failure / test rouge |
| `architecture-change.md` | ADR / migration / schéma / contrat / breaking change |
| `feature-development.md` | nouvelle fonctionnalité / brique / endpoint |
| `continuous-improvement.md` | améliorer la config / curator / agent roster / dette technique |

### Agents, slash commands, mise en route MCP, RTK

Documentation, pas déclencheurs : `.claude/dev-docs/tooling-reference.md`.
Les agents réellement invoqués le sont par les règles 5, 12, 13, 14, 17 ci-dessus
et par la règle de la boucle d'ingénierie — pas par un tableau.

### Hooks
- **UserPromptSubmit** → `inject_context.py` — keyword-triggered skill injection (domain patterns)
- **PostToolUse** → `check_python_syntax.py` — ruff after every Write/Edit; exit 2 blocks on E9 syntax errors
- **Stop** → `session_summary.py` — git diff (≤5 files), Docker health, turn count
→ Full specification: `.claude/hooks/hook.md`

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

**Deux fichiers, un seul actif** :

| Fichier | Contient | Lu par |
|---|---|---|
| `.claude/dev-docs/roadmap/checklist.md` | tâches et bugs **ouverts**, état de reprise | `/resume`, `/sprint`, hooks de fraîcheur |
| `.claude/dev-docs/roadmap/archive.md` | briques livrées, bugs clos — **passif** | personne en routine |

Resume after `/clear`: *"Read `.claude/dev-docs/roadmap/checklist.md` and continue with the next unchecked item."*

**Roadmap flow**: the top `## 📋 Tâches ouvertes` table is the concise index of only
*still-open* tasks. When a task is completed, run `/roadmap-done <id>` — it ticks the
detail line, **moves it into `archive.md`**, and retires the row from the index. For a
whole brick, `Spawn roadmap-keeper` (règle 17). Never hand-delete an item: déplacement,
pas suppression — `tests/test_roadmap_two_files.py` échoue si le total des deux fichiers
rétrécit.

| Bricks | Topic | Status | Priority |
|---|---|---|---|
| 1–8 | SaaS DB migration, Auth, Admin, Credentials, CSV import, Parameterized DAGs, iMusician, Home KPI | ✅ | — |
| 9–11 | Error handling + retry, Unit tests, Monitoring + alerting | ✅ | P2 |
| 12–13 | PDF export (WeasyPrint), CSV export (ZIP) | ✅ | P3 |
| 14 | FastAPI REST backend (JWT) | ✅ | P4 |
| 15 | CI/CD Railway deployment | ✅ | P4 |
| 16–17 | ML scoring DAG + ML dashboard views | ✅ | P3 |

---

## Tooling auxiliaire

### Graphify — local knowledge graph

This repo carries an indexed code graph in `graphify-out/` (**gitignored** — local
only). The MCP server in `.mcp.json` lets Claude Code query the graph; the
PreToolUse hook on `Glob|Grep` reminds to read `graphify-out/GRAPH_REPORT.md`
before brute-force searching files.

Refresh after significant code changes (≥ 5 files):

```bash
make graph                  # graph-update + graph-html in one shot
# OR step-by-step :
make graph-update           # refresh graph.json + GRAPH_REPORT.md (AST, no LLM)
make graph-html             # re-render graph.html from current graph.json
```

The graph currently indexes 1500+ nodes across 94 detected communities. If you
add or rename modules, regenerate so future `Glob`/`Grep` calls see the new
structure.

**Visual exploration** : open `graphify-out/graph.html` **directly in your
browser** (double-click, or `file://` URL). The HTML is standalone — vis-network
JS is bundled inline, no server needed. Features : click-to-inspect panel,
search box, community filter, physics layout, edge-confidence styling
(`EXTRACTED` solid vs `INFERRED` dashed). Generated by `make graph-html`, which
wraps `python3 tools/dev/graphify_render_html.py` — that script calls
`graphify.export.to_html` directly (the CLI doesn't expose this).

<!-- baseline-pointer v4 — source unique : tools/dev/claude-md-pointer.md du baseline.
     Ne pas éditer ici : éditer la source et relancer install_conformance_ratchet.py --write.
     Tout ce qui est entre ce marqueur et son marqueur de fin est REMPLACÉ à chaque
     déploiement. Le reste de ce CLAUDE.md n'est jamais touché. -->

## Configuration Claude Code — la conception

Quatre fichiers, quatre rôles, dans **`/mnt/c/Users/timot/Desktop/claude_code_deployment_baseline`** :

| Fichier | Répond à | Quand le lire |
|---|---|---|
| **`NEXT.md`** | *que faire ensuite ?* | **avant d'ouvrir une séance de travail sur la config** — c'est le backlog, chaque item avec son coût, son risque et sa commande de vérification |
| `ARCHITECTURE.md` | *pourquoi ?* | avant d'ajouter une skill, un agent ou un hook — §2 (budget) et §3 (ce qui fait qu'un composant se déclenche) |
| `REX.md` | *qu'a-t-on appris en se trompant ?* | avant d'écrire un installeur, un garde ou une métrique — les 14 entrées sont transverses aux 8 projets |
| `ROADMAP.md` | *qu'a-t-on fait ?* | pour l'état du parc et le journal |

Le fait le plus contre-intuitif, et le seul mesuré : **un agent nommé dans une règle
impérative de ce fichier est invoqué ; nommé dans un tableau ou une liste, il ne l'est
jamais** — 33 spawns contre 0 sur 23 agents.

```bash
python3 /mnt/c/Users/timot/Desktop/claude_code_deployment_baseline/tools/dev/audit_fleet.py --project . --markdown
python3 /mnt/c/Users/timot/Desktop/claude_code_deployment_baseline/tools/dev/verify_loop_wiring.py
```

### Règle contraignante — la boucle d'ingénierie

**≥2 trouvailles dans une même session → `RUN Workflow({name: "engineering-loop", args: [une chaîne par trouvaille]})`**, pas quatre lancements séparés.

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
