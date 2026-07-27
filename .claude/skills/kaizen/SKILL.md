---
name: kaizen
description: Continuous improvement through many small verified changes rather than one large rewrite. Use when the user asks to improve code quality, refactor, clean up, reduce technical debt, or discuss process improvement. Not for diagnosing a specific reported bug — systematic-debugging and impact-analysis cover that. Assumes working code that already passes its tests.
---

# Kaizen: Continuous Improvement

**Core principle:** Many small improvements beat one big change. Prevent errors at design time, not with fixes.

## The Four Pillars

### 1. Continuous Improvement
- Make smallest viable change that improves quality — one at a time
- Verify each change before moving to next
- Leave code better than you found it (fix small issues as you encounter them)
- Iteration order: make it work → make it clear → make it efficient (never all at once)

### 2. Error Proofing (Poka-Yoke)
- Prevent bad states at input boundaries — validate at the edge, trust internally
- Make wrong usage impossible (type hints, enums, Pydantic models)
- Fail fast with clear messages — no silent wrong behavior
- Design so common errors cannot occur, not just that they are handled

### 3. Standardization
- Follow existing patterns in the codebase before inventing new ones
- Document decisions that aren't obvious from the code
- Consistent naming: same concept → same name everywhere
- When you improve a pattern, update all instances (or leave a note)

### 4. Waste Elimination
- Remove dead code when you see it
- No speculative features — build only what is needed now
- No premature abstraction — three similar lines is better than a wrong abstraction
- No over-engineering: simplest correct solution wins

## this project-specific quality gates
- New endpoint → documented in endpoints.md + has at least one test
- New table column → migration in `_run_migrations()` + schema updated
- New background job → non-fatal failure, logs error, never crashes scheduler
- New ML model → a specialist reviewer criteria defined BEFORE training
- NCR / AMDEC update → reflected in ROADMAP.md + retro entry
