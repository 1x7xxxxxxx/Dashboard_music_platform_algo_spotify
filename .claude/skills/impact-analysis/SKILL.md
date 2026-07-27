---
name: impact-analysis
description: Sweeps the whole repository for sibling occurrences of a defect before any fix is written. Use whenever a bug, regression, drift, crash, 500, or false positive is identified — and always before patching it. It establishes blast radius only; it does not design the fix and is not a performance review. Assumes the failing symptom has already been identified.
---

# Skill: whole-repo impact analysis on a bug / divergence

**Load when** a bug, regression, drift, 500/crash, or false-positive is identified —
**before** writing the fix. A one-line patch that doesn't sweep the whole repo for
sibling occurrences leaves the same class of bug live elsewhere (the proven pattern here:
a silent-failure / wedge in one streaming consumer — a swallowed exception or a missing
socket timeout — repeated across `<consumer>`, `<consumer>`, `<consumer>`, `<consumer>`; fixing
only the reported consumer leaves the others wedging silently, 0 rows and no error).

## Why this exists (honesty)

The harness cannot *deterministically* detect "a bug was found" — that is a model
judgement. So this skill is the **reliable trigger**: it is auto-injected by
`inject_context.py` when ≥3 of the keywords above appear, and the CLAUDE.md
"bug → impact analysis" rule makes invoking it mandatory at the moment a defect is
identified. It is a playbook, not magic.

## Playbook (do these in order, do not skip 3)

1. **Reproduce / confirm.** Get the real symptom — traceback, failing test, drift
   diff, HTTP 500 body. Never fix from a guess about what's wrong.

2. **Root-cause by reading the code.** Open the actual failing path and the data it
   touches. Name the true cause (e.g. "handler selects `views`, column is
   `view_count` in the canonical schema"), not the surface symptom.

3. **Whole-repo impact sweep — the core step.** The bug is an *instance of a class*.
   Find every other instance:
   - `grep`/Grep the offending symbol, column, table, or pattern across **all** of
     `<module path>` (`api`, `ml`, `streaming`, `database`, `domain`, `bridges`,
     `observability`), `tools/`, the Alembic revisions, and the tests — not just the
     reported file.
   - For schema/contract drift: compare the live store against the Alembic head; for a
     silent-failure class, run `/audit-collectors` (R1–R4) across the streaming consumers.
   - For an error *class*: check `.claude/dev-docs/error-classes.md`; run
     `python3 .claude/scripts/audit_runner.py --all` to sweep every catalogued
     signature at once.
   - List each hit and decide: same bug (fix it now) or false alarm (note why).

4. **Long-term corrective = fix + a guard.** A fix without a guard re-rots. For
   each confirmed instance add ONE durable anti-recurrence mechanism:
   - a new **error-class signature** in `error-classes.md` (machine-detectable
     grep → swept by `audit_runner`, blocking CI if `kind: deterministic`), and/or
   - a **test** asserting the corrected behaviour, and/or
   - a **hook** reminder for the editing moment.

5. **Catalogue the learning.** Add/extend the error-class in `error-classes.md`.
   If the lesson is about a *Claude Code tool* (a hook/skill/command behaved
   wrong), add a `rex:` entry to that tool's frontmatter (issue ≤120, fix ≤200).

6. **Prod-sync if prod-affecting.** If the fix touches the DB schema / deploy scripts →
   reconcile via a new **Alembic revision** (`database/migrations/versions/`), never a manual
   ALTER on the IPC, and keep the deployed schema at the Alembic head. `check_prod_sync.py`
   will already have nudged you.

## Done criteria

- Every sibling occurrence found in step 3 is fixed or explicitly cleared.
- At least one guard (error-class / test / hook) blocks the *class*, not just the
  one site.
- If prod-affecting: a reconciling migration exists (no manual prod ALTER).
- The class is in `error-classes.md`; tool-lessons are in the tool's `rex:`.
