# CLAUDE.md

## Project Overview

Multi-tenant music analytics SaaS. ELT pipeline: external APIs and CSVs → Airflow DAGs (Docker) → PostgreSQL `spotify_etl` → Streamlit dashboard. Sources: Spotify API, Spotify for Artists CSV, Meta Ads, YouTube, SoundCloud, Instagram, Apple Music.

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

## .claude/ Tooling

### Cross-Cutting Rules (enforced in all code, comments, and responses)
1. **Language**: English exclusively — code, comments, docstrings, documentation.
2. **Neutrality**: Cold technical feedback. Enumerate trade-offs. No vibe-coding.
3. **Classification**: Label every module as Core/Feature/Sub/Hook/Utility with dependency verbs.
→ Full specification: `.claude/skills/response-protocol.md`

### Skills (`.claude/skills/`)
| File | Injected when |
|---|---|
| `dashboard-view.md` | "dashboard", "view", "streamlit" in prompt |
| `airflow-dag.md` | "dag", "airflow", "collector" in prompt |
| `db-schema.md` | "schema", "upsert", "postgres" in prompt |
| `response-protocol.md` | Always — defines cross-cutting rules |

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

### Hooks
- **UserPromptSubmit** → `inject_context.py` — keyword-triggered skill injection (domain patterns)
- **PostToolUse** → `check_python_syntax.py` — ruff after every Write/Edit; exit 2 blocks on E9 syntax errors
- **Stop** → `session_summary.py` — git diff, Docker health, turn count, pytest summary
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

Full checklist: `.claude/dev-docs/roadmap/checklist.md`
Resume after `/clear`: *"Read `.claude/dev-docs/roadmap/checklist.md` and continue with the next unchecked item."*

| Bricks | Topic | Status | Priority |
|---|---|---|---|
| 1–8 | SaaS DB migration, Auth, Admin, Credentials, CSV import, Parameterized DAGs, iMusician, Home KPI | ✅ | — |
| 9–11 | Error handling + retry, Unit tests, Monitoring + alerting | ✅ | P2 |
| 12–13 | PDF export (WeasyPrint), CSV export (ZIP) | ✅ | P3 |
| 14 | FastAPI REST backend (JWT) | 🔲 | P4 |
| 15 | CI/CD Railway deployment | 🔲 | P4 |
| 16–17 | ML scoring DAG + ML dashboard views | ✅ | P3 |
