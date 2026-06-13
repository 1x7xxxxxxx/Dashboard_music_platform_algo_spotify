---
rex: []
---

Mark a roadmap task complete: tick it in its detailed block AND remove its row from
the top `## 📋 Tâches ouvertes` index, recording it under `## Completed`.

The single source of truth is `.claude/dev-docs/roadmap/checklist.md` (no `ROADMAP.md`,
no `work-in-progress/`). Per CLAUDE.md, run this the moment a roadmap item is finished so
the top index always reflects only *still-open* work.

## Input

`/roadmap-done <id> [one-line note]` — `<id>` is the row id from the top table (e.g. `R3`),
or, if the task has no top-table row, an unambiguous substring of the task text.

## What to do

1. Read `.claude/dev-docs/roadmap/checklist.md`.

2. **Locate the task.** Find the row in `## 📋 Tâches ouvertes` whose `id` equals `<id>`,
   and its matching detailed `- [ ]` line further down (match by the task wording — the
   `R*` ids live only in the top index, the detail lines are prose, so match on content).
   If the id is ambiguous or not found, stop and list the candidate rows — do not guess.

3. **Tick the detail line:** change its `- [ ]` to `- [x]` and append ` ✅ (YYYY-MM-DD<,
   note if given>)` using today's date (read it from the environment's current date —
   never a bare `datetime.now()` assumption; convert relative to absolute).

4. **Remove the index row:** delete the task's line from the `## 📋 Tâches ouvertes` table.
   The top index must list ONLY open tasks.

5. **Record under `## Completed`:** add one line
   `- [x] <id> — <short task label> ✅ YYYY-MM-DD<, note>` to the `## Completed` section so
   the archive is the durable record (the detail block stays where it is, now ticked).

6. **Renumber? No.** Leave remaining `R*` ids as-is (ids are stable handles, not positions).

7. Report: the task ticked, the row removed, and how many open tasks remain in the index.

## Rules

- Never delete the detailed block — tick it in place (move = retire-from-index + tick, not
  erase). Mirrors the checklist-restructure principle: déplacement, pas suppression.
- One task per invocation. If the user passes several ids, process each in turn.
- If `<id>` maps to a task the checklist marks BLOCKED / awaiting a live data source, warn
  before ticking (it may not actually be done) and ask for confirmation.
- Touch only `checklist.md`. Do not commit — leave that to the user.
