---
name: subagent-driven-development
description: "Protocol for spawning fresh subagents per task with two-stage review. Use when planning multi-step implementations or spawning any background agent."
origin: superpowers (generic)
date_added: "2026-04-17"
rex: []
---

# Subagent-Driven Development

## When to Use

- Task modifies ≥ 2 files OR has multiple independent steps
- A `python-reviewer` / `security-reviewer` / `code-critic` pass is required
- Implementation + review must be in isolated contexts (no bias transfer)
- You need parallel exploration of independent areas

## Stage 1 — Spec-first subagent prompt

A good prompt has all 4 elements:

```
1. SCOPE       : exact file(s) + function(s) to add/modify
2. CONTRACT    : acceptance criteria — what proves success
                 (test name, smoke output, exit code, file exists)
3. CONSTRAINTS : project invariants the subagent must preserve
                 (parameterized queries only, no f-string SQL,
                  CM mandatory for connections, version pinned, ...)
4. OUTPUT      : what to write to disk + what to print as summary
```

Bad: "Fix the database issue"
Good: "In `database.py`, add `fetch_user_history(user_id, limit=50)` returning
       list[dict]. Use parameterized query (`%s` placeholders). Must pass
       `test_fetch_user_history` in test_database.py. Connection acquired via
       `with database.connection() as conn:`. Print PASS/FAIL of the test."

## Stage 2a — Spec compliance review

Before accepting subagent output, verify independently:

- [ ] Only the specified files were modified?
- [ ] Run acceptance criteria — do NOT trust the subagent's claim (`verification.md`)
- [ ] Project invariants preserved?

## Stage 2b — Code quality review

Spawn `code-critic` or `security-reviewer` on modified files:

```
Task: review changes to [file].
Focus: <pick from agent's responsibilities>.
Output: READY / WARN / BLOCK with file:line findings.
```

Accept only READY or WARN (no CRITICAL/HIGH findings unresolved).

## Agent budget

| Agent type | Model | Use for |
|------------|-------|---------|
| Orchestrator (you) | sonnet/opus | Planning, spec writing, review coordination |
| Implementer | sonnet | Single-file implementations |
| Code reviewer | sonnet | Code quality gate (`code-critic`, `security-reviewer`) |
| Architecture reviewer | opus | Cross-file refactor / Mermaid drift audit |
| Explore agents | haiku | Read-only codebase exploration (max 3 in parallel) |

## Anti-patterns

- Vague instruction ("do everything") → scope creep, unverifiable output
- Accept output without running tests → violates `verification.md`
- Implement and review in same context → reviewer inherits implementer's blind spots
- Spawn opus for simple file edits → use sonnet or haiku budget instead
- Run >3 Explore agents in parallel → context pollution, harder to reconcile findings
