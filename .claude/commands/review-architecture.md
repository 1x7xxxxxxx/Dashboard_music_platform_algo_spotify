---
rex: []
---

Audit Mermaid architecture diagrams against the actual codebase state.

## What to do

### Step 1 — Modules drift
Read `.claude/dev-docs/architecture/macro_architecture.md`.
List Python files in `src/Application/` (top-level only, exclude tests/, __pycache__, .venv).
For each major module (acquisition.py, api.py, database.py, background_ml.py, dashboard.py, features.py, processing.py, fanuc_reader.py, sensor_diagnostics.py, train_xgboost.py, train_autoencoder.py):
- ✅ if it appears in a diagram node
- ❌ if it exists on disk but is absent from all diagrams
- ⚠️  if it appears in a diagram but no longer exists on disk

### Step 2 — PostgreSQL tables drift (Alembic-managed)
Read `.claude/dev-docs/architecture/database_schema.md` — extract PG table names from the ERD.
List Alembic revisions under `src/Application/migrations/versions/` — each `op.create_table()` / `op.add_column()` defines the real schema.
Compare: report tables/columns in Alembic revisions but missing from ERD, and tables in ERD but not in Alembic chain (head `0012_add_rl_recommendations` as of 2026-04-24).

### Step 3 — QuestDB measurements drift
Read `.claude/dev-docs/architecture/database_schema.md` — extract QuestDB measurement names.
Grep `src/Application/` for ILP writes (`QUESTDB_ILP_PORT`, `questdb` TCP 9009 socket writes, `_write_rows_questdb`, `redis_consumer.py` bridge).
Report any measurement written in code but not documented, or documented but not found in code.

### Step 4 — Docker services drift
Read `.claude/dev-docs/architecture/macro_architecture.md` — extract service names.
Read `docker-compose.yml` at repo root — extract service names.
Report drift.

## Output format

Report as a checklist — one line per check, ✅ / ❌ / ⚠️.
End with: "X issues found. Run `/dev-docs fix-architecture-drift` to plan fixes." if any ❌ or ⚠️.
End with: "Architecture diagrams are in sync with codebase." if all ✅.

## When to use

- At session start after a long absence from the project
- Before a major refactor
- Before on-site IPC deployment (validate docs are current)
- After a new Alembic revision (to verify `database_schema.md` ERD matches head) or after adding a new QuestDB measurement (ILP write)
