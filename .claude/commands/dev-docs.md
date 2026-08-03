---
rex: []
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
- QuestDB measurements added/modified: ...
- PostgreSQL tables added/modified (via Alembic revision `NNNN_<desc>.py`): ...
- Redis Streams added/modified: ...
- New API endpoints: ...

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
- Last known test count: X/X passing

## QuestDB / PostgreSQL context
- QuestDB tables involved (ILP write path): ...
- PostgreSQL tables involved (metadata, managed by Alembic chain 0001 → 0012): ...
- Helper pattern to follow: `with database.connection() as conn:` + `database.insert_X / fetch_X` (never raw SQL outside `database.py`, never manual `get_connection() + close()`)

## Key files already read
- `src/Application/X.py` — role

## Patterns to follow
- Reference implementation: [file that has the closest existing pattern]

## Open questions
- Question 1 — what needs to be confirmed before implementing
- Question 2 — ...

## Resolved questions
- [Question text] → Answer (see DEVLOG YYYY-MM-DD or retro entry)
```

## Project context (for this feature)

**Stack:** STM32 STWIN → acquisition.py → QuestDB OSS | PostgreSQL 16 (metadata) → FastAPI :8000 → Streamlit :8501 / Grafana :3000. MLflow :5000 for model registry. Fanuc 30i+ via fanuc_reader.py (OPC UA :4840).

**Test command:** `cd src/Application && python3 -m pytest tests/ -v --tb=short`

**Dev-docs deliverables index:**
- `ROADMAP.md` — master project tracker (update when done)
- `REX.md` — append lessons learned
- `DEVLOG.md` — append session entry when done
- `architecture/macro_architecture.md` — system Mermaid
- `architecture/database_schema.md` — QuestDB measurements + PostgreSQL 16 ERD (21 tables)
- `architecture/stack_decision.md` — stack justification (QuestDB + PG, ADR-016)
- `architecture/cnc_connectivity.md` — Fanuc 30i+ details
- `features/feature_engineering.md` — 27 features
- `features/kpi_pipeline.md` — KPI flows
- `api/endpoints.md` — all endpoints
- `operations/alerting.md` — thresholds
- `mlops/cicd.md` — CI/CD
- `mlops/mlflow.md` — model registry

## After creating the files

Tell the user:
- Files created in `.claude/dev-docs/work-in-progress/$ARGUMENTS/`
- To resume after /clear: run `/resume` — it will load `context.md` (state + open questions) and `plan.md` (unchecked steps)
- When brick is complete: run through the closing checklist below before archiving

## Closing a brick (completion checklist)

Before moving the folder to `archives/brick-snapshots/`:
- [ ] All `- [ ]` steps in `plan.md` are checked off
- [ ] `ROADMAP.md` updated: brick marked ✅ with completion date
- [ ] `DEVLOG.md` entry appended (Why / What changed / test count)
- [ ] `context.md` — `## Open questions` section: all items either resolved (moved to `## Resolved questions`) or explicitly deferred with a note
- [ ] Test count stable — run `python3 -m pytest tests/ -q` and record count
- [ ] Move folder: `mv .claude/dev-docs/work-in-progress/$ARGUMENTS .claude/dev-docs/archives/brick-snapshots/$ARGUMENTS`
