---
name: continuous-learning
description: Captures a non-obvious pattern found during a session so it is not rediscovered later. Use at the end of a session, when the same fix or workaround appears a second time, when the user says "remember this", "save this pattern", or when a retro surfaces a recurring blocker. Not for writing project documentation or changelog entries — it persists reusable patterns only. Assumes the work being generalised from is already finished.
---

# Continuous Learning

## When to Use

- At the end of a session where you discovered a non-obvious pattern
- When the same fix or workaround appears for the second time
- When a constraint or anti-pattern needs to be remembered across sessions
- When `/retro` reveals a recurring blocker

## How to Save a Pattern

When a non-obvious pattern is confirmed (user doesn't push back, fix works):

1. Determine the scope:
   - **this project-specific** → save to `.claude/skills/learned/`
   - **Universal** → save to `~/.claude/skills/learned/`

2. Write the instinct file:

```markdown
---
trigger: "<when this situation occurs>"
confidence: 0.7
domain: "<postgres|migrations|collectors|airflow|dashboard|api|ml|docker|testing|tenant>"
discovered: "YYYY-MM-DD"
---

## Pattern
<one sentence>

## Evidence
- <what happened that revealed this>

## Action
<exactly what to do>

## Anti-pattern avoided
<what NOT to do>
```

3. Name the file descriptively: `postgres-bytea-decode-pattern.md`, `fastapi-nan-serialization.md`, `psycopg-pool-leak-under-threaded-uvicorn.md`

## this project Pattern Library — Discovered Patterns

Patterns confirmed and worth preserving across sessions:

### PostgreSQL / psycopg3
- `_nan_to_none()` required before `jsonable_encoder()` — MLflow run metrics return NaN which breaks JSON serialization
- `with database.connection() as conn:` CM — fires `putconn` on every exit path; manual `get_connection()+close()` leaks under threaded uvicorn (B54 Phase C)
- `ON CONFLICT (alert_id) DO UPDATE SET ...` for `alert_feedback` upsert — UNIQUE constraint on `alert_id`
- `np.frombuffer(blob, dtype='<f4')` for BYTEA decode — always little-endian float32
- Parameterized queries only (`%s` placeholders) — never f-string interpolation in SQL
- Alembic head check : `alembic upgrade head` on boot via `database.initialize_db()`, snapshot `schemas/schema_postgres.sql` is read-only

### FastAPI
- `with database.connection() as conn:` per route — CM fires putconn on every exit path (success/exception/pre-yield)
- `_xgb_bundle` loaded at startup — returns 503 if absent, never `None`-check in route handlers
- `_nan_to_none()` before all MLflow-sourced JSON responses

### Acquisition / STM32
- `BINARY_FRAME_SIZE = 3076` (4 magic + 768×4) — never hardcode 3072
- `raw[0::3]=X, raw[1::3]=Y, raw[2::3]=Z` — axis extraction from 768-float interleaved array
- Gyro magic = `0xBB66BB66`, accel magic = `0xAA55AA55`
- `ALERT_LOG_COOLDOWN_S` throttles log output independently from email cooldown

### ML
- SMOTE + cost-sensitive XGBoost weights — always both, not either/or
- `optimal_threshold` from JSON model card — never use 0.5 default for fault classification
- 27 features from `features.py` — shared between training and `/predict`, never diverge

### Testing
- `_pg_test_schema` (session autouse) creates `test_<worker>_<uuid>` schema via the psycopg pool, applies Alembic head, drops CASCADE on teardown
- `db_conn` fixture = TRUNCATE CASCADE across helper-managed tables on entry, yields pool connection
- `seeded_db` fixture = 5 rows (idle/running/fault) for last 5 hours via `database.insert_acquisition`
- Requires `docker compose up -d postgres` locally; CI uses a `postgres:16` service container

## Trigger Conditions for Saving

Save a pattern when:
- You had to look up the same thing twice in one session
- A bug fix required understanding a non-obvious constraint
- An anti-pattern caused a test failure that wasn't immediately obvious
- A workaround is specific to this project architecture (not general Python)
