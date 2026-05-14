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
2. Add to `pages` dict in `show_navigation_menu()` in `app.py`.
3. Add routing: `elif page == "<name>": from views.<name> import show; show()`.
→ Full patterns (DB queries, artist filter, role gate): `.claude/skills/dashboard-view.md`

### Adding a New DAG
1. Create `airflow/dags/<name>.py` with `sys.path.insert(0, '/opt/airflow')` at top.
2. Create `airflow/debug_dag/debug_<name>.py` for local testing.
3. `default_args`: owner, `depends_on_past=False`, `retries=2`, `retry_delay=timedelta(minutes=10)`.
→ Full patterns (credentials, in-task imports, failure callback): `.claude/skills/airflow-dag.md`

## Development tooling

| Topic | File / Command | Notes |
|---|---|---|
| Common commands | `Makefile` | `make help` lists 10 targets (up/down/logs/test/lint/migrate/dashboard/sync/clean). |
| Dependency manifest | `pyproject.toml` | Canonical project deps + dev extras. Adopted in Phase B (commit `9708b83`). |
| Lock file | `uv.lock` | Reproducible installs via `uv sync --frozen` (or `make sync`). 231 packages pinned. |
| Legacy install path | `requirements.txt` | Kept parallel for the existing Dockerfile + CI workflow. Dérivé de `pyproject.toml`. |
| Lint config | `ruff.toml` | Authoritative ruff config. `pyproject.toml [tool.ruff]` just extends it. |
| Ruff binary | `pip install ruff==0.15.5` (dev extra) | Available system-wide as `/home/timothe/.local/bin/ruff`. |

## Reference docs (dev-docs/)

When you need depth beyond `CLAUDE.md`, load these on demand :

| File | Content |
|---|---|
| `.claude/dev-docs/architecture/macro_architecture.md` | System Mermaid diagram + data flow |
| `.claude/dev-docs/architecture/database_schema.md` | Table inventory + ERD |
| `.claude/dev-docs/architecture/scripts_reference.md` | Module-by-module inventory |
| `.claude/dev-docs/architecture/stack_decision.md` | Why Postgres+Streamlit+Airflow vs alternatives |
| `.claude/dev-docs/ROADMAP.md` | ADR table (link to `docs/adr/`) |
| `.claude/dev-docs/roadmap/checklist.md` | Live brick tracker (open / completed) |
| `docs/adr/ADR-001-*.md` | Roadmap-multi-files-conserved decision |
| `docs/adr/ADR-002-*.md` | Rejected msdr patterns (Alembic, repo pattern, observability) |
| `docs/checklists_ml/RELEVANT_FOR_STREAMLYTICS.md` | ML checklist sections applicable here |
| `.claude/dev-docs/refactor-audit-dashboard.md` | Prioritized dashboard refactor pain points |

The graph at `graphify-out/GRAPH_REPORT.md` (auto-regenerated by `graphify update .`) is the **fastest way** to discover what's connected to what — read it before grepping.

## .claude/ Tooling

### Cross-Cutting Rules (always active — no file read needed)

Full specification: `.claude/skills/response-protocol.md` (load only for `/review-*` commands).

1. **Language**: English in all code, comments, docstrings, docs. Exception: Streamlit UI strings.
2. **Neutrality**: Cold technical feedback. State behavior + consequence. Enumerate ≥2 alternatives with trade-offs before recommending.
3. **Classification**: Label every new file in its docstring: `Type: Core|Feature|Sub|Hook|Utility` + `Uses/Triggers/Depends on/Persists in`.
4. **Priority**: P1 (crash/security) > P2 (data integrity) > P3 (UX) > P4 (tech debt). Never address P4 during a P1 session.
5. **Background agent**: Spawn `strategic-plan-architect` only after ≥3 files changed in one session. Not after single-file edits.
6. **Collectors must raise**: `except Exception` blocks in `src/collectors/` must always `raise` — never `return None`, `return []`, or `break` silently. Any deviation is a P2 data-integrity bug. Run `/audit-collectors` after touching any collector.
7. **`get_artist_id()` guard**: Never write `get_artist_id() or 1`. Always use the explicit guard:
   ```python
   artist_id = get_artist_id()
   if artist_id is None:
       if not is_admin(): st.error("Session invalide."); st.stop()
       artist_id = 1  # admin fallback — document explicitly
   ```
8. **SQL identifier allowlists**: Any f-string that interpolates a table name or column name must validate against a `frozenset` allowlist before execution. Values (user data) always use `%s` parameterization — never f-strings.
9. **DB connections per request**: `get_artist_plan()` uses 1 single LEFT JOIN query. Views must open 1 connection in `show()` and close it in `finally`. Never open `db2` as a fallback inside the same function.

### Skills (`.claude/skills/`) — load on demand via Skill tool only
| File | Use when |
|---|---|
| `dashboard-view.md` | Implementing a new Streamlit view from scratch |
| `airflow-dag.md` | Creating a new DAG or debug_dag |
| `db-schema.md` | Designing a new table or migration |
| `response-protocol.md` | Detailed audit rules — load only for `/review-*` commands |
| `audit-collectors.md` | Silent success anti-pattern rules — load for `/audit-collectors` or when touching collectors |

### Agents (`.claude/agents/`)
| Agent | Role |
|---|---|
| `strategic-plan-architect` | Background: updates architecture.md, retro.md, checklist.md, DEVLOG.md |
| `code-architecture-reviewer` | Cold audit of modified code vs project patterns |
| `build-error-resolver` | Diagnoses pytest failures when Stop hook signals ≥5 errors |
| `web-research-specialist` | Web research — returns ≤500-word distilled summary |

### Slash Commands
| Command | Purpose |
|---|---|
| `/review-db-schema` | Audit schema coherence (UNIQUE, upsert_many, artist filter) |
| `/review-dag` | Audit DAG conformity (sys.path, default_args, debug_dag coverage) |
| `/review-architecture` | Audit Mermaid diagrams vs current codebase state |
| `/logs-airflow` | Read + analyze recent Airflow container logs |
| `/dev-docs <name>` | Generate plan/context/checklist trio for a large feature |
| `/run-tests` | Execute pytest suite and analyze failures |
| `/audit-collectors` | Audit all collectors for silent success anti-pattern (see `.claude/skills/audit-collectors.md`) |

### Hooks
- **UserPromptSubmit** → `inject_context.py` — keyword-triggered skill injection (domain patterns)
- **PostToolUse** → `check_python_syntax.py` — ruff after every Write/Edit; exit 2 blocks on E9 syntax errors
- **Stop** → `session_summary.py` — git diff (≤5 files), Docker health, turn count
→ Full specification: `.claude/hooks/hook.md`

## MCP Servers

All configured in `~/.claude/settings.json` (never commit — contains credentials).

### spotify-postgres (active)
Direct SQL on `spotify_etl` via `mcp-postgres`. Requires Docker running.
```json
{ "spotify-postgres": { "command": "npx", "args": ["mcp-postgres"],
  "env": { "DB_HOST": "localhost", "DB_PORT": "5433", "DB_USER": "postgres",
            "DB_PASSWORD": "<see config.yaml>", "DB_NAME": "spotify_etl" } } }
```

### chrome-devtools (setup required)
Streamlit UI inspection, Lighthouse, console errors after UI modifications.
```json
{ "chrome-devtools": { "command": "npx", "args": ["-y", "@modelcontextprotocol/server-puppeteer"] } }
```

### sqlite (setup required)
Local SQLite files (e.g., MLflow tracking database if not using PostgreSQL backend).
```json
{ "sqlite": { "command": "npx", "args": ["-y", "@modelcontextprotocol/server-sqlite", "--db-path", "/path/to/db"] } }
```

### docker (setup required — WSL2 prerequisite)
Enable first: Docker Desktop → Settings → Resources → WSL Integration → enable distro.
```json
{ "docker": { "command": "docker", "args": ["run", "-i", "--rm", "-v", "/var/run/docker.sock:/var/run/docker.sock", "docker/mcp-toolkit"] } }
```

## Roadmap

Single master checklist: `.claude/dev-docs/roadmap/checklist.md`
Resume after `/clear`: *"Read `.claude/dev-docs/roadmap/checklist.md` and continue with the next unchecked item."*

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

### RTK (Rust Token Killer) — user-level proxy

If you see `rtk read`, `rtk pytest`, `rtk grep` in transcripts, that's the
**RTK** utility (user-level binary, not a project dependency) filtering and
compressing Bash output to save tokens (60-90 % typical, ~95 % at peak on this
machine). Transparent — no install or config needed on this repo.

- Pass-through any command : `rtk proxy <cmd>` (skip filtering, useful for
  debugging an output that RTK might have truncated).
- Inspect savings : `rtk gain` (global) / `rtk gain --history` (per-command).
- Identify missed opportunities : `rtk discover` (scans Claude Code history).

Reference: `~/.claude/RTK.md` (user-global config, not in this repo).

### Graphify — local knowledge graph

This repo carries an indexed code graph in `graphify-out/` (**gitignored** — local
only). The MCP server in `.mcp.json` lets Claude Code query the graph; the
PreToolUse hook on `Glob|Grep` reminds to read `graphify-out/GRAPH_REPORT.md`
before brute-force searching files.

Refresh after significant code changes (≥ 5 files):

```bash
make graph-refresh           # equivalent of: graphify update .
```

The graph currently indexes 1500+ nodes across 94 detected communities. If you
add or rename modules, regenerate so future `Glob`/`Grep` calls see the new
structure.

**Visual exploration** (cytoscape.js viewer) :

```bash
make graph-viewer            # serves on http://localhost:8765
# open http://localhost:8765/tools/graph_viewer.html
```

Interactive : click any node to see its source file, location, community, and
neighbors ; regex-filter labels via the search box ; switch layouts (fcose /
cose / circle / concentric / grid / breadthfirst) ; nodes are colored by
community. Standalone HTML, no install — cytoscape.js loads from CDN.
