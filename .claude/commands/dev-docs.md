---
rex:
  - date: 2026-08-21
    issue: "Every template field named another project's stack: QuestDB measurements, Alembic revisions `NNNN_<desc>.py` (rejected here by ADR-002), Redis Streams, `src/Application/X.py`, `with database.connection() as conn:`, and a 'Stack' line describing STM32 STWIN → QuestDB → Fanuc 30i+ over OPC UA. The deliverables index listed eight files that do not exist here and omitted the ones that do. A /dev-docs run would have produced a context.md that misdirects the next session after a /clear — the exact failure the command exists to prevent."
    fix: "Rewrote both templates and the project-context block against this repo: Postgres via PostgresHandler, plain-SQL migrations under migrations/, the tenant question made mandatory in the plan, and the deliverables index cut to files that exist."
    ref: "R36"
    severity: warn
---

Generate the documentation trio for a new feature/brick, to preserve context across conversation compaction.

Feature name: $ARGUMENTS

## What to create

Create two files under `.claude/dev-docs/work-in-progress/$ARGUMENTS/`:

### 1. `plan.md` — Implementation plan

```markdown
# $ARGUMENTS — Implementation Plan

## Objective
One sentence on what this brick/feature delivers.

## Affected files
| File | Nature (new / modified) | Role |
|------|------------------------|------|

## Implementation steps
1. Step 1 — specific, actionable
2. Step 2...

## Data flow changes
- Postgres tables added/modified (+ the `migrations/NNN_<desc>.sql` file): ...
- Schema definition updated in `src/database/<platform>_schema.py`: ...
- Collector / DAG touched: ...
- New dashboard view (+ its `_NAV_SECTIONS` entry in `app.py`): ...
- New API endpoint (+ its router): ...

## Tenant impact  ← mandatory, never "n/a" without a reason
- Which tables does this write? Are they tenant-scoped?
- Does every write payload carry `artist_id`, and is `artist_id` kept OUT of
  `update_columns`? (`python3 .claude/scripts/audit_tenant_writes.py`)
- Does any identity read fall back to an env var? It must not — env carries the
  ADMIN's identity (`.claude/rules/python.md`, ADR-006).

## Risks / watch-outs
- ...

## Out of scope
- ...
```

### 2. `context.md` — Technical snapshot (for resuming after /clear)

```markdown
# $ARGUMENTS — Technical Context

## Current state
- What already exists vs what is missing
- Last known test count: X passed / Y skipped (Postgres UP|DOWN)

## Database context
- Tables involved: ...
- Migration file: `migrations/NNN_<desc>.sql` — applied via `make migrate`
  (never a bare `psql`, never `< file` in PowerShell)
- Access pattern: `PostgresHandler` (`fetch_df` / `fetch_query` / `upsert_many`),
  `%s` placeholders only; a table or column name interpolated into an f-string
  validates against a `frozenset` allowlist first (cross-cutting rule #8)
- Views open exactly one connection via `view_session()` (rule #9)

## Key files already read
- `src/...` — role

## Patterns to follow
- Reference implementation: [the closest existing file]
- Relevant skill: `dashboard-view/` · `airflow-dag/` · `db-schema/`

## Open questions
- Question 1 — what needs confirming before implementing
- Question 2 — ...

## Resolved questions
- [Question text] → Answer (see DEVLOG YYYY-MM-DD)
```

## Project context (for this feature)

**Stack:** external APIs + CSV → Airflow DAGs (Docker) → PostgreSQL `spotify_etl`
(port 5433 locally) → Streamlit dashboard :8501, plus a FastAPI REST backend (JWT).
Sources: Spotify API, Spotify for Artists CSV, Meta Ads, YouTube, SoundCloud,
Instagram, Apple Music.

**Test command:** `python3 .claude/scripts/select_tests.py` to pick the set, then
`python3 -m pytest tests/ -q`. Report the skip count — ~128 tests are DB-gated.

**Dev-docs deliverables index** (files that exist):
- `.claude/dev-docs/roadmap/checklist.md` — the ACTIVE tracker. Rotate a finished
  item with `/roadmap-done <id>`; a whole brick with `Spawn roadmap-keeper`. Never
  hand-delete: `tests/test_roadmap_two_files.py` fails if the two files' total shrinks.
- `.claude/dev-docs/roadmap/archive.md` — delivered / closed, passive
- `DEVLOG.md` (repo root) — append a session entry when done
- `.claude/dev-docs/architecture.md` — **the** architecture surface: system Mermaid,
  data flow, table inventory, Views Map
- `.claude/dev-docs/error-classes.md` — one entry per defect class (`/capitalise`)
- `docs/adr/ADR-NNN-*.md` — architectural decisions (`/adr`)

## After creating the files

Tell the user:
- Files created in `.claude/dev-docs/work-in-progress/$ARGUMENTS/`
- To resume after /clear: run `/resume` — it loads `context.md` (state + open
  questions) and `plan.md` (unchecked steps)
- Delete the folder when the brick ships — `/resume` skips folders marked
  `COMPLETED`, but a stale folder still costs a read every session
