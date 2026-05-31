---
rex:
  - date: 2026-05-31
    issue: "sprint read .claude/dev-docs/ROADMAP.md which does not exist in this repo"
    fix: "Repointed to the single source of truth .claude/dev-docs/roadmap/checklist.md"
    severity: warn
---

Generate a concise session start-up summary from the roadmap checklist.

## What to do

1. Read `.claude/dev-docs/roadmap/checklist.md` (the single source of truth — there
   is no `ROADMAP.md`).

2. Output a compact status in this format (plain text, no tables):

**Current Sprint — streaMLytics**
Date: YYYY-MM-DD

Open P1/P2 items (actionable now):
- <unchecked `- [ ]` item under a P1 or P2 section> — <section>
- ...

P3 / P4 backlog:
- <count> P3 open (<1-line theme>) · <count> P4 open (<1-line theme>)

Blocked (live data source / deploy-gated):
- <unchecked items the checklist marks BLOCKED or awaiting Phase-2 data / deploy>

Last completed:
- <last 3 `[x]` items added near the bottom (WAVE / ML decision layer sections)>

3. Keep the output under 20 lines. No markdown tables. The goal is a quick mental
   reload at session start without reading all 400+ lines of checklist.md.

## When to use

Run `/sprint` at the start of any new session to orient. For a per-item resume
with branch + ADRs, use `/resume` instead.
