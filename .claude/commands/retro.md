---
invocation: "manual — the draft_rex/promote_rex pipeline it drove was retired (R417: 657 drafts pending, 0 promoted in 48 sessions)"
rex: []
---

Write a durable lesson into the colocated `rex:` block of the `.claude/` tool it concerns.

## What to do

1. List the tools under `.claude/{agents,skills,commands,rules,hooks,scripts}/` modified this
   session (`git status --short`, `git log` since the session start). Most edits do not
   warrant an entry — only a lesson that will surprise a future reader.
2. For each, draft an entry conforming to `.claude/rules/rex-format.md`:
   ```yaml
   - date: YYYY-MM-DD
     issue: "≤120 chars — symptom observed"
     fix: "≤200 chars — concrete action taken"
     ref: "Rnnn or commit"   # optional
     severity: info | warn | crit            # optional, default info
   ```
3. Show the drafts to the user; append only the validated ones to the tool's `rex:` list.
4. Run `python3 .claude/scripts/validate_rex.py --strict`.

## Rules

- REX entries are immutable once written. To correct, add a new entry with `ref:` pointing to the original.
- No tool meaningfully modified → no entry. Do not invent REX entries.
