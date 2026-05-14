---
rex: []
---

Resume the current session context after a /clear or session restart.

## What to do

1. Read `.claude/dev-docs/ROADMAP.md` — extract only the `## Current Sprint` section.

2. List files in `.claude/dev-docs/work-in-progress/` (excluding README.md). For each subfolder found:
   - Read the first 10 lines of `context.md` — **skip the folder entirely** if it contains `COMPLETED` or `BRICK COMPLETE` (it should have been archived; ignore it silently)
   - Otherwise: read **full** `context.md` — show the `## Current state` section AND the `## Open questions` section (list all unanswered questions)
   - Read `plan.md` — show objective and remaining steps (unchecked `- [ ]` items only)

3. Read the last 5 entries from `DEVLOG.md` (repo root) — show title + "What changed" lines only, no full body.

4. Read `.claude/dev-docs/archives/_archived_retro.md` — scan the **last 3 entries** for lines containing `Next session:`, `Deferred`, `⬜`, or `prochaine session`. Surface them as **Deferred actions** (max 4 items, skip if none found). Also read `.claude/sessions/pending-rex.md` if it exists and list any un-promoted REX drafts (session cleanup reminder).

5. Read `.claude/dev-docs/ROADMAP.md` — scan the `## Architecture Decision Records` section. Show the 2 ADRs most relevant to the active WIP bricks (match by brick name, technology keyword, or domain). Show: ADR number + title + one-line rationale. Skip if no WIP is active.

6. Output a compact session brief in this format:

---
**Session Brief — YYYY-MM-DD**

**Active sprint:**
<P1 items from Current Sprint, 3 lines max>

**Work in progress:**
<feature name> — <one-line state>
  Open questions: <questions from ## Open questions, one per line>
(or "None — start a new feature with /dev-docs <name>")

**Deferred from last sessions:**
- <deferred action or Next session item>
(omit section if nothing deferred)

**Relevant ADRs:**
- ADR-XXX: <title> — <rationale>
(omit section if no WIP active)

**Last changes:**
- YYYY-MM-DD: <DEVLOG title>
- ...

**Suggested next action:**
<first unchecked P1 item from ROADMAP.md Active Development>
---

7. If no work-in-progress folder exists and no P1 is open: tell the user the project is in a clean state and suggest running `/sprint` for a full status.

## When to use

Run `/resume` as the very first command after any `/clear` or new session start when a feature was in progress.
Order: `/resume` first → then work. Not `/sprint` (that's for roadmap overview only).
