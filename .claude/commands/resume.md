---
rex:
  - date: 2026-05-31
    issue: "resume read ROADMAP.md + work-in-progress/ — neither exists here, so /resume returned nothing useful"
    fix: "Repointed to the single source of truth .claude/dev-docs/roadmap/checklist.md + docs/adr/ + the Stop-hook session snapshot"
    severity: warn
---

Resume the current session context after a /clear or session restart.

The **single source of truth** for this project is
`.claude/dev-docs/roadmap/checklist.md` (there is no `ROADMAP.md` and no
`work-in-progress/` here — do not look for them).

## What to do

1. Read `.claude/dev-docs/roadmap/checklist.md`. Extract **only the still-open
   items** (`- [ ]`). Group them by the priority of their enclosing section
   heading (P1 > P2 > P3 > P4). Ignore everything under `## Completed`, and ignore
   `[x]` items. There are typically ~20 open items — summarise, don't dump all.

2. Read the latest session snapshot the Stop hook writes (auto-loaded into context
   at session start under "Session State"). Surface its `## Git branch`,
   `## Git status`, and `## Active WIP` lines. If it is absent, skip silently.

3. Read the last 5 entries from `DEVLOG.md` (repo root) — show title + "What
   changed" lines only, no full body.

4. If `.claude/sessions/pending-rex.md` exists, list any un-promoted REX drafts
   (session-cleanup reminder).

5. Scan `docs/adr/` (files `ADR-0NN-*.md`). Show the 1–2 ADRs most relevant to the
   open P1/P2 items (match by keyword/domain). Show: ADR number + title +
   one-line rationale. Skip if nothing relevant.

6. Output a compact session brief in this format:

---
**Session Brief — YYYY-MM-DD**

**Branch:** <branch> (<clean | N files modified>)

**Open — by priority (from checklist.md):**
- P1: <open P1 items, or "none">
- P2: <open P2 items, max 4>
- P3: <count> open (<1-line theme>)
- P4: <count> open (<1-line theme>)

**Relevant ADRs:**
- ADR-XXX: <title> — <rationale>
(omit if none relevant)

**Last changes:**
- YYYY-MM-DD: <DEVLOG title>
- ...

**Suggested next action:**
<the highest-priority open item that is actionable now — skip items the checklist
marks as BLOCKED / awaiting a live data source / deploy-gated>
---

7. If no open P1/P2 items remain: tell the user the actionable backlog is clear
   and the rest is P3/P4 or blocked, then suggest `/sprint` for the full picture.

## When to use

Run `/resume` as the very first command after any `/clear` or new session start.
Order: `/resume` first → then work.
