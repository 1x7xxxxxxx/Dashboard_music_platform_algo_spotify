---
description: "Concise session start-up summary from the active roadmap."
rex:
  - date: 2026-08-03
    issue: "Read `.claude/dev-docs/ROADMAP.md` (an unrendered bootstrap template) and asked for `Completed Bricks` / `Active Development` sections that existed there only as TODO placeholders. Its output format also described MSDR bricks and 'waiting on hardware' — another project."
    fix: "Repointed to `.claude/dev-docs/roadmap/checklist.md` (actif) and rewrote the output around the real sections: 📋 Tâches ouvertes, 🔖 REPRISE, Open Bugs."
    ref: "roadmap-two-files-2026-08-03"
    severity: warn
---

Generate a concise session start-up summary from the active roadmap.

## What to do

1. Read `.claude/dev-docs/roadmap/checklist.md` — the **active** file. It holds only open
   work, so it is short. Never read `archive.md` for this: it is passive by contract, and
   nothing in it is actionable.

2. Output a compact status in this format (plain text, no tables):

**Sprint — streaMLytics**
Date: YYYY-MM-DD

Actionable now:
- <items from the `## 📋 Tâches ouvertes` index whose statut is neither BLOQUÉ nor DIFFÉRÉ>

Blocked (and on what):
- <id — the blocker named in the statut column, verbatim; never paraphrase a blocker>

Open bugs:
- <unchecked items under `## Open Bugs`, highest priority first>

State of play:
- <2 lines max from `## 🔖 REPRISE`>

3. Keep the output under 20 lines. No markdown tables. The goal is a quick mental reload.

4. Do not count DIFFÉRÉ items as backlog: each carries an explicit trigger ("déclencheur :
   ≥50 artistes", "trafic concurrent"). Reporting them as pending work manufactures urgency
   the roadmap deliberately parked.

## When to use

At the start of a session, to orient without reading the whole file. Use `/resume` instead
when a feature was mid-flight — that one reloads work-in-progress context too.
