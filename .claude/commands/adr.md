---
description: "Add an Architecture Decision Record as a standalone file in docs/adr/."
rex:
  - date: 2026-08-03
    issue: "The command wrote ADRs into a table in `.claude/dev-docs/ROADMAP.md`, a bootstrap template never rendered (it still held literal `$(date +%Y-%m-%d)`). Its Context section described another project — QuestDB, Fanuc OPC UA, Airbus IT/OT. Six real ADRs meanwhile lived as standalone files in docs/adr/, which the command never named."
    fix: "Rewrote against docs/adr/: next number read from the directory, file created from ADR-TEMPLATE.md, project context corrected to streaMLytics."
    ref: "roadmap-two-files-2026-08-03"
    severity: warn
---

Add an Architecture Decision Record to `docs/adr/`.

ADR subject: $ARGUMENTS

## What to do

1. `ls docs/adr/` — the next number is the highest `ADR-NNN-*.md` plus one, zero-padded
   to three digits. Do not renumber or reuse: an ADR is immutable once merged, and a
   superseded one is marked `Superseded by ADR-YYY`, never edited away.

2. Create `docs/adr/ADR-NNN-<kebab-slug>.md` from `docs/adr/ADR-TEMPLATE.md`. Fill every
   section. The two that carry the weight:

   - **Alternatives rejected** — at least one real option with the reason it lost. An ADR
     with a single option is a rationalisation written after the fact, not a decision.
   - **Consequences → Negative / Trade-offs** — what this costs. An ADR with no negative
     consequence has not been thought through.

3. If the decision changes something a reader would otherwise assume, add the pointer where
   that reader actually is — `CLAUDE.md`, the relevant rule, or the skill — not only here.

4. Tell the user: `ADR-NNN added — docs/adr/ADR-NNN-<slug>.md`, and name what it invalidates.

## Context — this project

ADRs here cover: roadmap file layout (ADR-001), rejected msdr patterns incl. Alembic
(ADR-002), the React rewrite deferral that keeps Streamlit (ADR-003), S4A stream sourcing
by manual entry over scraping (ADR-004), the split-VPS deployment topology (ADR-005), and
the central credential model (ADR-006).

Status lives in the roadmap, never here: `.claude/dev-docs/roadmap/checklist.md` for what is
open, `.claude/dev-docs/roadmap/archive.md` for what shipped. An ADR records *why*; it does
not track progress.
