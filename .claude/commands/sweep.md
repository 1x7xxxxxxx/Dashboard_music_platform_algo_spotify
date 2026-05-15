---
rex: []
---

Turn a discovered bug into a catalogued **error class** with a machine-detectable
signature, sweep the whole project for other instances, and wire (or recommend)
a durable guard so it cannot recur.

This command **orchestrates** existing tooling — it never re-implements
`/review-dag`, `/review-db-schema`, `/review-architecture`, or the audit agents.
It owns: abstraction → signature → project-wide sweep → guard wiring → catalogue.

## Input

`$ARGUMENTS` is either:
- a free-text bug description (e.g. "make dashboard crashed because Postgres was down"), or
- an existing `CLASS-ID` from `.claude/dev-docs/error-classes.md` (e.g. `streamlit-pin-drift`).

Single source of truth = `.claude/dev-docs/error-classes.md`. Read it first.

## Phase 0 — Resolve the class

- If `$ARGUMENTS` matches a `CLASS-ID` in the catalogue, load that section.
- Else abstract the bug: name it (`kebab-case`), write the one-line `symptom`,
  and derive a **machine-detectable `signature`** that exits non-zero on a hit.
  Prefer, in order: a `ruff` rule > a `grep -rnE`/AST one-liner > a script.
  Wrap greps as `! grep -rnE '<pat>' <path>` so a hit is a non-zero exit.
- If a near-duplicate class already exists, **reuse it** (extend its History;
  never fork a second class for the same root cause).
- Decide `kind`: `deterministic` (zero false positives — safe to block CI) or
  `heuristic` (grep approximation — nightly non-blocking only).

## Phase 1 — Sweep the project

- Before raw grep, consult `graphify-out/GRAPH_REPORT.md` god-nodes when the
  class is structural (call-site oriented). The signature grep is authoritative;
  the graph is advisory.
- Execute `signature.cmd` literally from the repo root. Collect every hit as
  `file:line`.
- For DAG-shaped classes delegate to `/review-dag`; schema-shaped →
  `/review-db-schema`; architecture drift → `/review-architecture`; deep
  semantic audits → spawn the `code-architecture-reviewer` or
  `security-specialist` agent. Aggregate their findings; do not duplicate them.

## Phase 2 — Prioritised report

Group hits and assign a priority per CLAUDE.md Cross-Cutting Rule #4
(P1 crash/security > P2 data integrity > P3 UX > P4 tech debt). Use the
`/review-dag` output convention — do not invent a new format:

```
[P1] src/foo.py:42 — <what is wrong here>
[P3] Makefile:18 — <what is wrong here>
Summary: N hits — P1×a P2×b P3×c P4×d
```

## Phase 3 — Recommend a durable guard

Pick from the fixed menu, enumerating ≥2 options with trade-offs before the
recommendation (CLAUDE.md Rule #2):

| Class nature | Default guard |
|---|---|
| Mechanical, AST-expressible | `ruff` rule (config in `ruff.toml`) |
| Manifest / file-shape, deterministic | pre-commit local hook **+** blocking `ci.yml` step |
| Edit-time footgun in one file type | `PostToolUse` hook (mirror `lint_dashboard_view.py`) |
| Heuristic, false-positive-prone | `make audit` signature **+** nightly job (never block CI) |
| Makefile precondition | the `check-env` prerequisite pattern (Rule #10) |
| Semantic / architectural | cross-cutting rule (CLAUDE.md + `.claude/rules/`) + report-only |

Deterministic → may block CI. Heuristic → nightly only (flaky-red CI erodes the
gate — this is why rules #6–#10 live in `make audit`, not `ci.yml`).

## Phase 4 — Apply fixes (safe classes only)

- If the catalogue class is `autofix: safe` (e.g. `streamlit-pin-drift`,
  `df-na-rep`): apply the **mechanical** fix to the exact hits only — nothing
  else. State each file changed.
- If `autofix: none` (auth guards `#7`, SQL allowlists `#8`, collector raise
  `#6`, `make-fail-late`): **report only**. Propose the patch in the report;
  do not edit. Hard rule: *never rewrite unrelated code unasked* (CLAUDE.md).

## Phase 5 — Record + close the loop

- Upsert the class section in `.claude/dev-docs/error-classes.md`:
  `status: guarded` if a guard was wired this run, else `reported` (instances
  found, no guard yet) or `open`. Append a dated **History** line — never
  rewrite prior lines (append-only).
- Self-check: confirm the catalogue `signature.cmd` and the hardcoded `make audit`
  recipe still match; if drifted, report it (known documented debt).
- Record the durable lesson via the existing REX path — **do not hand-edit any
  `rex:` block**. Append a block to `.claude/sessions/pending-rex.md` targeting
  the guard tool (per-tool class) or note it belongs in CLAUDE.md + the relevant
  `.claude/rules/` file (architectural class, per `rex-format.md` taxonomy).
  The Stop chain `promote_rex.py` (or `/rex-promote`) injects it; immutability
  and the ≤120/≤200/severity schema are enforced by `validate_rex.py`.

## Edge cases

1. **No hits** — the bug was a one-off. Still catalogue it (`status: guarded`
   if a guard prevents recurrence) so the signature exists for future sweeps.
2. **Signature too noisy** (>~50 hits, mostly false) — downgrade `kind` to
   `heuristic`, keep it out of CI, note the false-positive shape in History.
3. **Class already `guarded`** — re-run the signature to confirm zero
   regressions; if hits reappeared, append a History line, do not duplicate.
4. **Cannot derive a signature** — record the class `status: open` with a prose
   detection note; do not invent a flaky grep just to have one.

## When to use

- After diagnosing any bug, to check the rest of the project for the same class.
- When `.claude/hooks/suggest_sweep.py` prints the bugfix-shaped-session hint.
- Periodically with a `CLASS-ID` to re-verify a `guarded`/`reported` class.
