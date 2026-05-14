---
rex: []
---

Generate a concise session start-up summary from ROADMAP.md.

## What to do

1. Read `.claude/dev-docs/ROADMAP.md`.

2. Output a compact status in this format (plain text, no tables):

**Current Sprint — {{PROJECT_NAME}}**
Date: YYYY-MM-DD

Active bricks (P1 open items only):
- Brick XX — <name>: <first unchecked P1 item>
- ...

Next P2 items:
- <up to 3 unchecked P2 items across all active bricks>

Blocked / waiting on hardware:
- <bricks with explicit "waiting" notes>

Last completed:
- <last 3 rows added to the Completed Bricks table>

3. Keep the output under 20 lines. No markdown tables. The goal is a quick mental reload at session start.

## When to use

Run `/sprint` at the start of any new session to orient without reading all 300+ lines of ROADMAP.md.
