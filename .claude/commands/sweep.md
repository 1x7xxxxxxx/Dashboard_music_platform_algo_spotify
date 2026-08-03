---
rex: []
---

Turn a discovered bug into a catalogued **error class** with a machine-detectable
signature, sweep the whole project for other instances, and wire (or recommend)
a durable guard so it cannot recur.

This command **orchestrates** existing tooling — it never re-implements a
`/review-*` command or an audit agent. It owns: abstraction → signature →
project-wide sweep → guard wiring → catalogue.

## Input

`$ARGUMENTS` is either:
- a free-text bug description, or
- an existing `CLASS-ID` from `.claude/dev-docs/error-classes.md`.

Single source of truth = `.claude/dev-docs/error-classes.md`. Read it first.
If the catalogue does not exist yet, create it from its template (the schema +
contract block) before adding the first class.

## Phase 0 — Resolve the class

- If `$ARGUMENTS` matches a `CLASS-ID`, load that section.
- Else abstract the bug: name it (`kebab-case`), write the one-line `symptom`,
  derive a **machine-detectable `signature`** that exits non-zero on a hit.
  Prefer, in order: a linter rule > a `grep -rnE`/AST one-liner > a script.
  Wrap greps as `! grep -rnE '<pat>' <path>` so a hit is a non-zero exit.
- Reuse a near-duplicate class if one exists (extend its History; never fork).
- Decide `kind`: `deterministic` (zero false positives — safe to block CI) or
  `heuristic` (grep approximation — nightly non-blocking only).

## Phase 1 — Sweep the project

- For structural/call-site classes, consult the code graph report (if the
  project ships one) before raw grep. The signature is authoritative.
- Execute `signature.cmd` literally from the repo root. Collect every hit as
  `file:line`.
- If a `/review-*` command or an audit agent already covers this domain,
  delegate to it and aggregate its findings — do not duplicate the audit.

## Phase 2 — Prioritised report

Group hits and assign a priority per the project's priority tiers
(P1 crash/security > P2 data integrity > P3 UX > P4 tech debt):

```
[P1] path/to/file.py:42 — <what is wrong here>
Summary: N hits — P1×a P2×b P3×c P4×d
```

## Phase 3 — Recommend a durable guard

Pick from the fixed menu, enumerating ≥2 options with trade-offs first:

| Class nature | Default guard |
|---|---|
| Mechanical, AST-expressible | linter rule |
| Manifest / file-shape, deterministic | pre-commit local hook **+** blocking CI step |
| Edit-time footgun in one file type | `PostToolUse` hook |
| Heuristic, false-positive-prone | an aggregator target **+** nightly job (never block CI) |
| Build/Make precondition | a fail-fast prerequisite at the top of the build target |
| Semantic / architectural | a cross-cutting rule (CLAUDE.md + `.claude/rules/`) + report-only |

Deterministic → may block CI. Heuristic → nightly only (flaky-red CI erodes the
gate).

## Phase 4 — Apply fixes (safe classes only)

- If the catalogue class is `autofix: safe`: apply the **mechanical** fix to the
  exact hits only — nothing else. State each file changed.
- If `autofix: none` (semantic — auth, SQL, control flow…): **report only**.
  Propose the patch; do not edit. Hard rule: *never rewrite unrelated code
  unasked*.

## Phase 5 — Record + close the loop

- Upsert the class section in `.claude/dev-docs/error-classes.md`:
  `status: guarded` if a guard was wired, else `reported`/`open`. Append a dated
  **History** line — never rewrite prior lines (append-only).
- If an aggregator target hardcodes signatures, confirm it still matches the
  catalogue; report drift.
- Record the durable lesson via the existing REX path — **do not hand-edit any
  `rex:` block**. Append a block to `.claude/sessions/pending-rex.md` targeting
  the guard tool, or note an architectural class belongs in CLAUDE.md + the
  relevant `.claude/rules/` file (per `rex-format.md` taxonomy). The Stop chain
  (`draft_rex.py`) drafts it and `/rex-promote` injects it; immutability + the
  schema are enforced by the REX validator.

## Edge cases

1. **No hits** — a one-off. Still catalogue it so the signature exists later.
2. **Too noisy** (>~50 mostly-false hits) — downgrade `kind` to `heuristic`,
   keep it out of CI, note the false-positive shape.
3. **Already `guarded`** — re-run the signature; if regressions reappeared,
   append a History line, do not duplicate.
4. **No derivable signature** — record `status: open` with a prose detection
   note; do not invent a flaky grep.

## When to use

- After diagnosing any bug, to check the rest of the project for the class.
- When `suggest_sweep.py` prints the bugfix-shaped-session hint.
- Periodically with a `CLASS-ID` to re-verify a `guarded`/`reported` class.
