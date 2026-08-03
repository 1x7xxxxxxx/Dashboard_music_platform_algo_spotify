---
description: "Rotate a finished roadmap task out of the active file into the archive."
rex:
  - date: 2026-08-03
    issue: "Step 5 wrote the completion line into a `## Completed` section of checklist.md. The 2026-08-03 two-file split moved that section to archive.md, so the step named a heading that no longer exists in the file it opens."
    fix: "Rewrote for the two files: tick, move the detail block into archive.md, retire the index row, then run the conservation test."
    ref: "roadmap-two-files-2026-08-03"
    severity: warn
---

Mark a roadmap task complete and **rotate** it: ticked, moved out of the active file, into
the archive, index row retired.

The roadmap is two files:

| Rôle | Fichier |
|---|---|
| actif — ce qui est ouvert | `.claude/dev-docs/roadmap/checklist.md` |
| archive — ce qui est livré ou clos | `.claude/dev-docs/roadmap/archive.md` |

Run this the moment an item is finished, so the active file always reflects only still-open
work. For a whole brick (rather than a single row) prefer `Spawn roadmap-keeper` — same
contract, and it recounts aggregates when the file carries any.

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

4. **Move the ticked line** — cut it from `checklist.md`, paste it into `archive.md` under
   the section it belongs to (create the `## <section>` heading there if absent). Cut and
   paste, in that order, in one edit each: an item duplicated across both files is counted
   twice and reads as two deliveries.

5. **Remove the index row:** delete the task's line from the `## 📋 Tâches ouvertes` table.
   The active index must list ONLY open tasks.

6. **Renumber? No.** Leave remaining `R*` ids as-is (ids are stable handles, not positions).

7. **Verify the rotation conserved everything:**
   ```bash
   python3 -m pytest tests/test_roadmap_two_files.py -q
   ```
   It fails if the two files together hold fewer items than before, or if an unchecked box
   landed in the archive. If it goes red, restore and say where the item was lost — do not
   lower the floor in the test to make it pass.

8. Report: the task ticked, where it landed, the row removed, how many open tasks remain,
   and the test result.

## Rules

- **Déplacement, pas suppression.** Removing a task from the active file without adding it
  to the archive raises the completion percentage without delivering anything — the measure
  improves because reality shrank. That is the failure this whole two-file split exists to
  make visible.
- One task per invocation. If the user passes several ids, process each in turn.
- If `<id>` maps to a task the checklist marks BLOQUÉ / awaiting a live data source, warn
  before ticking (it may not actually be done) and ask for confirmation.
- Touch only the two roadmap files. Do not commit — leave that to the user.
