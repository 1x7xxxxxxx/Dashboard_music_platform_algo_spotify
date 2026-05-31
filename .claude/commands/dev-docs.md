---
rex:
  - date: 2026-05-31
    issue: "/dev-docs listed ROADMAP.md as the master tracker, a file that does not exist in\
  \ this repo"
    fix: "Repointed to .claude/dev-docs/roadmap/checklist.md as the single source of truth\
  \ (there is no ROADMAP.md)"
    severity: "warn"
    ref: "DEVLOG#2026-05-31"
---

Generate the documentation trio for a new feature/brick, to preserve context across conversation compaction.

Feature name: $ARGUMENTS

## What to create

Two files under `.claude/dev-docs/work-in-progress/$ARGUMENTS/`:

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
2. Step 2 ...

## Data / state changes
- New tables / columns / measurements: ...
- New env vars / secrets: ...
- New external integrations: ...

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

## Stack context
- Languages / frameworks involved: ...
- Data stores touched: ...
- External services consumed: ...

## Key files already read
- path/to/file.ext — role

## Patterns to follow
- Reference implementation: [file with the closest existing pattern]
- Conventions: see `.claude/rules/*.md`

## Open questions
- Question 1 — what needs to be confirmed before implementing
- Question 2 — ...

## Resolved questions
- [Question text] → Answer (see DEVLOG YYYY-MM-DD)
```

## Project context (for this feature)

Fill in your own. Suggested template:

**Stack:** <data source> → <ingestion> → <store> → <api> → <ui>

**Test command:** `<your test runner>`

**Dev-docs deliverables index:**
- `.claude/dev-docs/roadmap/checklist.md` — the single source of truth (master tracker; there is no `ROADMAP.md`)
- `DEVLOG.md` — append session entry when done
- `architecture/macro_architecture.md` — system Mermaid
- `architecture/database_schema.md` — schema (if applicable)
- `api/endpoints.md` — endpoints (if applicable)
- `operations/alerting.md` — alerting (if applicable)
- (other dev-docs your project relies on)

## After creating the files

Tell the user:
- Files created in `.claude/dev-docs/work-in-progress/$ARGUMENTS/`
- To resume after /clear: run `/resume`
- When brick is complete: run the closing checklist below before archiving

## Closing a brick (completion checklist)

- [ ] All `- [ ]` steps in `plan.md` checked off
- [ ] `.claude/dev-docs/roadmap/checklist.md` updated: item checked `[x]` with completion date
- [ ] `DEVLOG.md` entry appended (Why / What changed / verification evidence)
- [ ] `context.md` Open questions: resolved or deferred
- [ ] Tests / smoke checks recorded
- [ ] Move folder: `mv .claude/dev-docs/work-in-progress/$ARGUMENTS .claude/dev-docs/archives/brick-snapshots/$ARGUMENTS`
