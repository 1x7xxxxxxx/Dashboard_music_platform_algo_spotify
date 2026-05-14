---
rex: []
---

Promote validated REX drafts from `.claude/sessions/pending-rex.md` into each target tool's `rex:` frontmatter block.

## Input

`.claude/sessions/pending-rex.md` contains one `## <file>` section per modified tool. Each section has a fenced YAML block:

```yaml
target: <file>
validated: false | true
entry:
  date: YYYY-MM-DD
  issue: "..."
  fix: "..."
  severity: info | warn | crit
  # ref: DEVLOG#YYYY-MM-DD or brick id    # optional
```

## What to do

1. Read `.claude/sessions/pending-rex.md`. If absent or contains no `## <file>` section → print "No REX drafts pending" and stop.

2. For each section, in file order:
   - Parse the fenced YAML block.
   - If `validated` is not `true`, or `entry.issue` / `entry.fix` is `"?"` or empty → skip (remain pending).
   - Else: open `target` and inject `entry` into its `rex:` list:
     - **`.md` file**: the `rex:` key is in the frontmatter YAML block at the top (`---\n...\n---`). Append the entry as a new item.
     - **`.py` file**: the `rex:` key is inside the YAML block delimited by `---\n...\n---` within the module docstring. Append there.
   - Preserve chronological order (append to tail).

3. After the pass:
   - If every section was promoted → delete `pending-rex.md`.
   - Else → rewrite `pending-rex.md` keeping only the unpromoted sections.

4. Run `python3 .claude/scripts/validate_rex.py`. Fail cleanly (report the error, don't retry) if the validator exits non-zero.

5. Report to the user: `Promoted N REX entries into M files. K drafts remain pending.`

## Rules

- **Never edit** `entry.issue`, `entry.fix`, `entry.severity`, or `entry.date` — inject verbatim from the validated block. The human owns the content.
- **Never inject** into files outside `.claude/{agents,skills,commands,rules,hooks,scripts}`.
- **Never overwrite** an existing REX entry — only append new ones. Corrections are new entries with `ref:` pointing to the original.
- **Abort cleanly** on malformed YAML: report which target + why, preserve `pending-rex.md`, do not partially write.

## When to use

- End of session after `draft_rex.py` has populated `pending-rex.md` and the user has filled in `issue` + `fix` + `validated: true`.
- When `/retro` asks to run the injection step as a focused sub-flow.
- Manually, when `pending-rex.md` was hand-edited to add proposals outside the automated capture.
