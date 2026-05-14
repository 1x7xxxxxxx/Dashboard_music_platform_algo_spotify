---
name: kaizen
description: "Guide for continuous improvement, error proofing, and standardization. Use this skill when the user wants to improve code quality, refactor, or discuss process improvements."
risk: unknown
source: community
date_added: "2026-02-27"
rex: []
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
- Make wrong usage impossible (type hints, enums, Pydantic models, exhaustive `match`)
- Fail fast with clear messages — no silent wrong behavior
- Design so common errors cannot occur, not just that they are handled

### 3. Standardization
- Follow existing patterns in the codebase before inventing new ones
- Document decisions that aren't obvious from the code (ADR, code comment with `# why`)
- Consistent naming: same concept → same name everywhere
- When you improve a pattern, update all instances (or leave a note)

### 4. Waste Elimination
- Remove dead code when you see it
- No speculative features — build only what is needed now
- No premature abstraction — three similar lines is better than a wrong abstraction
- No over-engineering: simplest correct solution wins

## Project-specific quality gates

(Populate this section in your project's own `.claude/skills/kaizen.md`. Examples:)

- New endpoint → documented in `api/endpoints.md` + has at least one test
- New table column → migration committed + ERD updated
- New background job → non-fatal failure path, logs error, never crashes scheduler
- New dependency → license check + pinned version + entry in `dependencies.md`
- New external integration → entry in `architecture/integrations.md` + credential ID documented
