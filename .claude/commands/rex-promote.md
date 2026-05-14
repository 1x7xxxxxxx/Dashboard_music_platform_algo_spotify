---
rex:
  - date: 2026-05-14
    issue: "Manual issue/fix fill step left pending-rex.md stubs un-promoted across sessions"
    fix: "Rewrote command as 3 phases (Suggest from observations.jsonl + git diff + file re-read\
  \ + DEVLOG, then delegate to promote_rex.py, then validate); lifted human-owned-content\
  \ rule"
    severity: "info"
    ref: "DEVLOG#2026-05-14"
---

Auto-suggest + auto-promote REX drafts from `.claude/sessions/pending-rex.md` into each target tool's `rex:` frontmatter block.

When `issue:` / `fix:` are stubs (`"?"`) or the block is not yet `validated: true`, this command **generates the entry text from the session context** and promotes in one shot. The previous manual-validation contract is lifted in favor of an automatic flow — see `.claude/rules/rex-format.md § Auto-fill via /rex-promote`. The hard schema constraints (date ISO, ≤120 / ≤200 chars, severity allowlist, target dir allowlist) still apply and are enforced by `validate_rex.py`.

## Input

`.claude/sessions/pending-rex.md` contains one `## <file>` section per modified tool. Each section has a fenced YAML block :

```yaml
target: <file>
validated: false | true
entry:
  date: YYYY-MM-DD
  issue: "?" | "..."
  fix: "?" | "..."
  severity: info | warn | crit
  # ref: DEVLOG#YYYY-MM-DD or brick id    # optional
```

## Phase 0 — Bootstrap

1. Read `.claude/sessions/pending-rex.md`. If absent or no `## <file>` section → print `No REX drafts pending` and stop.
2. Parse each fenced YAML block. Keep `target`, `validated`, `entry` per block.

## Phase 1 — Suggest (auto-fill stubs)

For each block where (`validated` is `false`) OR (`entry.issue == "?"`) OR (`entry.fix == "?"`) :

### A. Gather context (4 sources, in order)

1. **observations.jsonl snippets** — read `.claude/homunculus/<repo-name>/observations.jsonl` (`<repo-name>` = repo root dir name, e.g. `Dashboard_music_platform_algo_spotify`). Filter JSON lines where `file` resolves to the target's absolute path AND `ts` is on/after the session start (read `.claude/sessions/.session-start-ts`, Unix float; fallback to the last 2h if absent). Collect `edit.old` / `edit.new` pairs (80 chars each) for `tool: Edit`; for `tool: Write` log `full rewrite`.
2. **git log + git diff** — run :
   ```bash
   START_ISO=$(awk '{printf "%d", $1}' .claude/sessions/.session-start-ts | xargs -I{} date -u -d @{} -Iseconds)
   git log --since="$START_ISO" --oneline -- <target>
   git diff HEAD -- <target>
   ```
   Captures committed changes + working-tree diff for the file.
3. **Full re-read of `target`** — `Read` the file end-to-end to see the post-edit structure (frontmatter, allowed dirs, hook chain, etc.).
4. **Last DEVLOG entry** — read the first ~80 lines of `.claude/dev-docs/DEVLOG.md`. If the top header `## YYYY-MM-DD …` matches `entry.date`, capture its title — use it as `ref: DEVLOG#YYYY-MM-DD`.

### B. Generate `issue` + `fix`

- **`issue`** ≤120 chars — symptom observed or gap filled (NOT the fix). Pattern : `<area> <past verb> <consequence>`. Examples from existing entries :
  - `"Hook was a no-op: _INCLUDE='src/Application' mismatched repo, tracker paths pointed to archived/non-existent files"`
  - `"Mermaid update target was architecture/macro_architecture.md, a stub archived this session"`
- **`fix`** ≤200 chars — concrete action taken. Examples :
  - `"Repointed to roadmap/checklist.md + DEVLOG.md, _INCLUDE='src' with hook/script/test excludes"`
  - `"Replaced 'append to retro.md' with 'append to per-tool REX block per rex-format.md'"`
- **`severity`** heuristic :
  - `crit` → fix on a crash, silent-failure, data-integrity bug
  - `warn` → no-op repaired, deprecation, masked bug, missing guard
  - `info` → new feature, extension, instructions added (default)
- **`ref`** → `DEVLOG#YYYY-MM-DD` only if the date matches a real DEVLOG header captured in source #4 ; otherwise omit.
- **`date`** → keep verbatim from the block (already filled by `draft_rex.py` in UTC ISO).

### C. Update the block in memory

Set `validated: true`, overwrite `entry.issue` / `entry.fix` / `entry.severity` with the generated values, add `entry.ref` if applicable. Do **not** write `pending-rex.md` yet — Phase 2 handles persistence.

## Phase 2 — Promote

For each block now validated (auto-filled or already validated by hand) :

1. **Sanity-check the target** : must start with one of `.claude/{agents,skills,commands,rules,hooks,scripts}/` and the file must exist. Otherwise skip with `reason: target outside allowed dirs / not found`.
2. **Sanity-check the entry** : `date` matches `^\d{4}-\d{2}-\d{2}$`, `len(issue) ≤ 120`, `len(fix) ≤ 200`, `severity ∈ {info, warn, crit}`. If a generated suggestion exceeds the char limit, **reformulate once** (no brutal truncation) ; if still over → skip with `reason: schema violation after 1 retry`.
3. **Delegate the injection to `promote_rex.py`** :
   - Write the updated blocks back to `pending-rex.md` with `validated: true` and the filled `issue` / `fix` / `severity` / optional `ref`.
   - Run `python3 .claude/scripts/promote_rex.py`. This script handles the YAML-list append into `.md` frontmatters and `.py` docstring blocks (logic at `_inject_md` / `_inject_py` / `_append_entry_to_yaml_block`), preserves chronological order, deletes `pending-rex.md` when fully promoted, and emits stderr summary lines.
   - Capture its stderr — those lines (`REX auto-promote: …`) are the source of truth for what got injected.
4. **Append-only contract** : never overwrite an existing entry. Corrections require a new entry with `ref:` pointing to the original (rex-format.md rule, unchanged).

## Phase 3 — Cleanup & validate

1. If `promote_rex.py` cleared everything → `pending-rex.md` is already deleted by the script. Otherwise it persists with the leftover unpromoted blocks (cases : target missing, schema violation, no context available).
2. Run `python3 .claude/scripts/validate_rex.py`. If exit non-zero, report the error verbatim — do **not** retry, do **not** revert (injections are append-only and idempotent ; a manual rerun after fixing is safe).
3. Final report to the user, format :
   ```
   Auto-suggested + promoted N REX entries into M files.
   Skipped K drafts (reason: <…>).
   Validator: OK | <error summary>
   ```

## Edge cases

1. **Target has zero context** — all 4 sources empty (no observations entry, no git history since session start, file unchanged on disk, DEVLOG silent). Skip with `reason: no context available — manual edit required`. Keep the block in `pending-rex.md`.
2. **Manual edits without Edit/Write tool** — file modified outside Claude Code (e.g. external editor). observations.jsonl misses it ; sources #2 (git diff) and #3 (re-read) compensate.
3. **Recursion** — when this command injects into `.claude/agents/foo.md`, `observe.py` logs the edit, so the next Stop's `draft_rex.py` will propose a new draft for `foo.md` (about the REX injection itself). This is acceptable noise — the user can delete the stub block at next session. Not worth filtering at the hook layer.
4. **Suggestion above char limit** — reformulate once, then skip if still over (`reason: schema violation after 1 retry`).
5. **`promote_rex.py` already ran at the previous Stop** — if every block was already validated and injected by the Stop hook chain, Phase 0 finds no pending blocks and exits early.

## Rules (post-2026-05-14)

- **Auto-fill is allowed** for `issue` / `fix` / `severity` / `ref` when stubbed. The human-owned-content rule is lifted ; format constraints (date, char limits, severity allowlist) remain enforced by `validate_rex.py`.
- **Never inject** into files outside `.claude/{agents,skills,commands,rules,hooks,scripts}`.
- **Never overwrite** an existing REX entry — append-only ; corrections = new entry with `ref:`.
- **Abort cleanly** on malformed pending-rex.md YAML : report which target + why, preserve `pending-rex.md`, do not partially write.

## When to use

- End of session after `draft_rex.py` has populated `pending-rex.md`. No need to hand-fill anymore — just call this command.
- When `/retro` invokes the REX injection sub-flow.
- Manually, when `pending-rex.md` was hand-edited (auto-fill detects existing non-stub content and leaves it untouched, only promoting).

## Manual fallback (legacy contract preserved)

To keep the old strict workflow (human owns the content, no auto-fill) : edit `pending-rex.md` by hand to fill `issue` + `fix` + set `validated: true`, then call `python3 .claude/scripts/promote_rex.py` directly (it's also the Stop-hook auto-promoter and refuses entries with stubs). The slash command's Phase 1 is skipped only when every block is already non-stub and validated.
