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
→ Full patterns (DB queries, artist filter, role gate): `.claude/skills/dashboard-view.md`

### Adding a New DAG
1. Create `airflow/dags/<name>.py` with `sys.path.insert(0, '/opt/airflow')` at top.
2. Create `airflow/debug_dag/debug_<name>.py` for local testing.
3. `default_args`: owner, `depends_on_past=False`, `retries=2`, `retry_delay=timedelta(minutes=10)`.
→ Full patterns (credentials, in-task imports, failure callback): `.claude/skills/airflow-dag.md`

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
| `.claude/dev-docs/roadmap/checklist.md` | Live brick tracker (open / completed) |
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

Full specification: `.claude/skills/response-protocol.md` (load only for `/review-*` commands).

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
11. **Bug → whole-repo impact analysis**: the moment a bug, divergence, regression, drift, or 500/crash is identified, load `.claude/skills/impact-analysis.md` and follow it **before** writing the fix. A defect is an instance of a *class* — sweep the whole repo for sibling occurrences (the proven `/kpis` → `/youtube` drift lesson), root-cause by reading the code (not guessing), and ship fix **+ a durable guard** (error-class signature / test / hook) so the class can't recur. The skill is auto-injected by `inject_context.py` on ≥2 bug-keywords; this rule makes it mandatory regardless. If prod-affecting, finish with `make sync-check`.

### Skills (`.claude/skills/`) — load on demand via Skill tool only
| File | Use when |
|---|---|
| `dashboard-view.md` | Implementing a new Streamlit view from scratch |
| `airflow-dag.md` | Creating a new DAG or debug_dag |
| `db-schema.md` | Designing a new table or migration |
| `response-protocol.md` | Detailed audit rules — load only for `/review-*` commands |
| `audit-collectors.md` | Silent success anti-pattern rules — load when touching collectors |
| `impact-analysis.md` | A bug/divergence/drift/500 was identified — whole-repo impact sweep + root-cause + durable guard (rule #11; auto-injected on bug-keywords) |

### Agents (`.claude/agents/`)
| Agent | Role |
|---|---|
| `strategic-plan-architect` | Background: updates architecture.md, checklist.md, DEVLOG.md + per-tool REX blocks |
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

### Required setup before first use

1. **Export env vars** in `~/.bashrc` or `.env.local` (see `.env.example` § MCP Servers) :
   ```bash
   export DB_PASSWORD='<see config/config.yaml>'
   export GITHUB_TOKEN='<PAT scopes: repo, read:org>'   # github.com/settings/tokens
   export AIRFLOW_ADMIN_USERNAME='<see docker-compose.yml — _AIRFLOW_WWW_USER_USERNAME>'
   export AIRFLOW_ADMIN_PASSWORD='<see docker-compose.yml — _AIRFLOW_WWW_USER_PASSWORD>'
   ```
2. **Chromium / Chrome auto-downloaded** by `chrome-devtools-mcp` on first run via puppeteer (no `apt install` needed). On WSL2 Ubuntu 24.04, the `chromium-browser` apt package is a snap shim that doesn't work — rely on puppeteer's bundled Chrome for Testing instead.
3. **Install `uv`** if missing (for `airflow` MCP) : `pip install uv`
4. **Restart Claude Code** so it re-reads `.mcp.json`.

### Verification
- `claude mcp` lists active servers and start-up errors
- Each MCP can be tested by asking Claude an obvious query (e.g. "list spotify_etl tables", "list open PRs", "list DAGs and their status")

### MCP selection rationale (May 2026)
- **Postgres MCP** : official Anthropic server, read-only by default — safer than `crystaldba/postgres-mcp-pro` for exploratory use
- **GitHub MCP** : official GitHub (Go-based) — supersedes the legacy TS `@modelcontextprotocol/server-github`
- **Chrome DevTools MCP** : official Google server — supersedes the older `@modelcontextprotocol/server-puppeteer`
- **Airflow MCP** : community `yangkyeongmo/mcp-server-apache-airflow` — no official Apache/Astronomer equivalent yet

### Out-of-scope (intentionally excluded)
- MLflow / Sentry MCPs : aucune dépendance détectée dans le repo
- Filesystem / Sequential-thinking MCPs : redondants avec les outils natifs de Claude Code
- Notion / Gmail / Drive : déjà disponibles côté Claude.ai (deferred tools)
- Spotify Web API MCP : redondant avec `src/collectors/spotify_collector.py`

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
