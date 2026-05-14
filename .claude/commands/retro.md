---
rex: []
---

Capture lessons from the current session into the colocated `rex:` block of each affected tool.

## What to do

1. Check `.claude/sessions/pending-rex.md` first — the `draft_rex.py` Stop hook may already have drafted proposals from this session's edits.
   - If present: go to step 3.
   - If absent: go to step 2.

2. **Manual drafting** (fallback when the hook did not fire or mid-session capture is needed):
   - Run `git status --short` + review `observations.jsonl` tail for files modified this session.
   - For each modified tool under `.claude/{agents,skills,commands,rules,hooks,scripts}/`, decide whether a durable lesson was extracted — most edits do not warrant a REX entry, only ones that will surprise a future reader.
   - For each eligible tool, draft a block conforming to `.claude/rules/rex-format.md`:
     ```yaml
     - date: YYYY-MM-DD
       issue: "≤120 chars — symptom observed"
       fix: "≤200 chars — concrete action taken"
       ref: "DEVLOG#YYYY-MM-DD or brick id"   # optional
       severity: info | warn | crit            # optional, default info
     ```

3. **Review** each proposal from `pending-rex.md` (or the drafts from step 2):
   - Ask the user to validate issue + fix + severity. Reject entries without a clear durable lesson — REX is not a change-log.
   - Set `validated: true` on entries to keep. Delete blocks for rejected proposals.

4. **Promote** — delegate to `/rex-promote`:
   ```
   /rex-promote
   ```
   This reads `pending-rex.md`, injects validated entries into target frontmatters, runs the validator, and cleans up.

5. If the promotion step fails (validator error, malformed YAML in a target), fix the underlying issue and re-run `/rex-promote`. `/retro` itself should never hand-edit target files — that is `/rex-promote`'s job.

## Rules

- REX entries are immutable once promoted. To correct, add a new entry with `ref:` pointing to the original.
- Never write to `archives/_archived_retro.md` or `archives/_archived_REX.md` — they are frozen historical archives.
- If no tool under `.claude/` was meaningfully modified this session, `/retro` is a no-op — do not invent REX entries.
