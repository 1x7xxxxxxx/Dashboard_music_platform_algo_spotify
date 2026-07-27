---
name: subagent-driven-development
description: Spawns a fresh subagent per task under a two-stage spec-then-review protocol. Use when planning a multi-step implementation, when a change touches two or more modules, or before spawning any background agent. Not for single-file edits, where the orchestration overhead exceeds the benefit. Assumes the task can be split into independently reviewable steps.
---

# Subagent-Driven Development

## When to Use

- Task modifies ≥ 2 files in `<module path>`
- Plan has multiple independent steps
- A a specialist reviewer, a specialist reviewer, or a specialist reviewer pass is required
- Implementation + review must be in isolated contexts (no bias transfer)

## Stage 1 — Spec-first subagent prompt

A good prompt has all 4 elements:

```
1. SCOPE    : exact file(s) + function(s) to add/modify
2. CONTRACT : acceptance criteria — which test name proves success
3. CONSTRAINTS : this project invariants (BINARY_FRAME_SIZE=3076, WAL mode,
                  parameterized queries only, connection closed in finally)
4. OUTPUT   : what to write to disk + what to print as summary
```

Bad: "Fix the database issue"
Good: "In `database.py`, add `fetch_hole_quality_history(hole_id, limit=50)`
       returning list[dict]. Parameterized query. Must pass
       `test_fetch_hole_quality_history` in test_database.py.
       Connection must close in finally block."

## Stage 2a — Spec compliance review

Before accepting subagent output, verify independently:

- [ ] Only the specified files were modified?
- [ ] Run acceptance criteria tests — do NOT trust subagent's claim (`verification-before-completion.md`)
- [ ] this project invariants preserved?

## Stage 2b — Code quality review

Spawn `a specialist reviewer` on modified files:

```
Task: review changes to [file.py].
Focus: SQL injection, exception handling, secret leakage.
Output: READY / WARN / BLOCK with file:line findings.
```

Accept only READY or WARN (no CRITICAL/HIGH findings unresolved).

## this project Agent Budget

| Agent type | Model | Use for |
|------------|-------|---------|
| Orchestrator | sonnet | Planning, spec writing, review coordination |
| Implementer | sonnet | Single-file implementations |
| a specialist reviewer | sonnet | Code quality gate |
| a specialist reviewer | opus | Model training/evaluation only |
| Explore agents | haiku | Read-only codebase exploration (max 3) |

## Anti-patterns

- Vague instruction ("do everything") → scope creep, unverifiable output
- Accept output without running tests → violates `verification-before-completion.md`
- Implement and review in same context → reviewer inherits implementer's blind spots
- Spawn opus for simple file edits → use sonnet or haiku budget instead
