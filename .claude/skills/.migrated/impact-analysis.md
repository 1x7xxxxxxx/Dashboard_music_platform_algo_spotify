---
keywords: bug, divergence, régression, regression, drift, 500, crash, broken, broke, faux positif, false positive, root cause, root-cause, impact, sync, hotfix, traceback, exception, stacktrace
rex: []
---

# Skill: whole-repo impact analysis on a bug / divergence

**Load when** a bug, regression, drift, 500/crash, or false-positive is identified —
**before** writing the fix. A one-line patch that doesn't sweep the whole repo for
sibling occurrences leaves the same class of bug live elsewhere (the proven
`/kpis` → `/youtube/videos` lesson: identical schema-drift in a second handler,
missed because only the reported endpoint was fixed).

## Why this exists (honesty)

The harness cannot *deterministically* detect "a bug was found" — that is a model
judgement. So this skill is the **reliable trigger**: it is auto-injected by
`inject_context.py` when ≥2 of the keywords above appear, and CLAUDE.md rule #11
makes invoking it mandatory at the moment a defect is identified. It is a
playbook, not magic.

## Playbook (do these in order, do not skip 3)

1. **Reproduce / confirm.** Get the real symptom — traceback, failing test, drift
   diff, HTTP 500 body. Never fix from a guess about what's wrong.

2. **Root-cause by reading the code.** Open the actual failing path and the data it
   touches. Name the true cause (e.g. "handler selects `views`, column is
   `view_count` in canonical schema"), not the surface symptom.

3. **Whole-repo impact sweep — the core step.** The bug is an *instance of a class*.
   Find every other instance:
   - `grep`/Grep the offending symbol, column, table, pattern across **all** of
     `src/`, `airflow/`, `tools/`, `migrations/`, tests — not just the reported file.
   - For schema/column drift: run `python3 tools/dev/schema_drift_check.py` (or
     `make schema-check PROD_SSH=…`) — prod↔canonical column diff.
   - For an error *class*: check `.claude/dev-docs/error-classes.md`; run
     `python3 .claude/scripts/audit_runner.py --all` to sweep every catalogued
     signature at once.
   - List each hit and decide: same bug (fix it now) or false alarm (note why).

4. **Long-term corrective = fix + a guard.** A fix without a guard re-rots. For
   each confirmed instance add ONE durable anti-recurrence mechanism:
   - a new **error-class signature** in `error-classes.md` (machine-detectable
     grep → swept by `audit_runner`, blocking CI if `kind: deterministic`), and/or
   - a **test** asserting the corrected behaviour (e.g. `test_api_db_smoke.py`
     caught the /youtube drift), and/or
   - a **hook** reminder for the editing moment.

5. **Catalogue the learning.** Add/extend the error-class in `error-classes.md`.
   If the lesson is about a *Claude Code tool* (a hook/skill/command behaved
   wrong), add a `rex:` entry to that tool's frontmatter (issue ≤120, fix ≤200).

6. **Prod-sync if prod-affecting.** If the fix touches `migrations/`, `init_db.sql`,
   `src/database/*`, or deploy scripts → run `make sync-check PROD_SSH=…`
   (schema-drift + deploy-drift) and reconcile via a **migration**, never a manual
   ALTER on prod. `check_prod_sync.py` will already have nudged you.

## Done criteria

- Every sibling occurrence found in step 3 is fixed or explicitly cleared.
- At least one guard (error-class / test / hook) blocks the *class*, not just the
  one site.
- If prod-affecting: `make sync-check` is green or a reconciling migration exists.
- The class is in `error-classes.md`; tool-lessons are in the tool's `rex:`.
