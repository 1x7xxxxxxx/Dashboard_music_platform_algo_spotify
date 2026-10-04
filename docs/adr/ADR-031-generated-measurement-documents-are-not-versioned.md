# ADR-031 — Generated measurement documents are generated on demand, not versioned

- **Status:** Accepted
- **Date:** 2026-10-04
- **Deciders:** the owner (« est-ce que c'est pertinent de conserver la mise à jour auto des docs ? … on pourrait optimiser notre temps »), R345, code-critic BUILD-MODIFIED

## Context

Four documents were written by generators and committed:
`.claude/dev-docs/error-class-health.{md,json}`, `error-class-families.md` and `gold-coverage.md`.
Measured on 2026-10-04:

| question | measure |
|---|---|
| how often they changed | **302 of 652 commits** since 2026-09-20 touched one of them (15 646 lines) |
| who read them | the gates that checked they were fresh; the owner reads none of them, and runs the generator when they want a number |
| what freshness cost | 2 red CI runs of the 2026-10-04 session alone, plus a pre-commit hook (`gold-coverage-fresh`), three `--check` targets and two tests that existed only to say « regenerate » |

The ratchets need the **numbers**, not the files: every ceiling is written by hand in a test,
and the test compares the computed counters to it.

## Decision

1. The four documents leave git (`git rm --cached`, named in `.gitignore`). `make error-health`,
   `make error-families` and `make gold-coverage` still write them into the working tree.
2. The ratchets and the tools that read the payload (`error_debt.py`, `reopen_check.py`,
   `error_class_metrics.py`, the families' recurrence column) compute it for the tree via
   `tools/dev/generated_cache.py`: a file cache keyed by the tree hash git would commit
   (throwaway index + `git add -A` + `write-tree`) and shared across xdist workers under
   `flock`. Cold ≈ 7 s (health) + 20 s (gold); warm ≈ 0.2 s.
3. `error_class_health.py --check` stays in CI, reduced to what it can still judge: the
   **ranking** of `error-classes.md` (a tracked file the generator writes).
4. The replay refuses a shallow clone (`require_full_history`), because a truncated history
   gives plausible, wrong recurrences. Prod is a shallow clone: `tools/deploy.sh` unshallows it.
5. The time series that lived in the git history of the JSON is recomputed from the history of
   the catalogue (`make error-health-history` → `error_debt_trend.py --series`); the history
   before 2026-10-04 stays readable with `git log -p -- .claude/dev-docs/error-class-health.json`.
6. `error-inbox.md` stays versioned: it is a work list, clock-independent since R342.

Guard: `tests/test_generated_documents_are_not_versioned.py`.

## Alternatives rejected

- **Keep them versioned, drop only the staleness gates.** The committed files would then go
  stale silently, which is worse than absent: they read exactly like a fresh measurement
  (`a-generated-document-asserts-a-stale-state`).
- **Keep them versioned, regenerate in a post-commit hook.** Same churn, plus a hidden write
  in every commit.
- **Delete the generators.** That loses the ratchets (they need the computation) and the
  on-demand view the owner does use.
- **An in-process `lru_cache` instead of a file cache.** Each xdist worker is a separate process
  and would pay the 27 s computation itself (code-critic, R345).

## Consequences

- No commit carries a regenerated document any more; `make catalogue-sync` is now ranking + durations.
- The first test that reads a counter on a new tree pays the cold computation once for all workers.
- Anyone who needs the document runs the `make` target; nothing in git can be out of date.
