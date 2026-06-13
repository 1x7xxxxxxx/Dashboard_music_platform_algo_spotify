---
rex: []
---

Run the config self-improvement curator and act on its proposals (with validation).

The curator (`/curator`) is the ported `hermes` loop: it makes the Claude Code config
*improve each iteration* by surfacing redundancy (near-duplicate REX / error-classes),
real usage (what actually fires), and dead weight (stale skills, cold guards). It is
**report-only** — it proposes, you validate, mirroring `/rex-promote`.

## What to do

1. Run the analyzer:
   ```bash
   python3 .claude/scripts/curator.py --stale-days 30
   ```
   (tune `--stale-days` / `--threshold` if the user asks for a tighter/looser pass).

2. Read its three sections and act **only with the user's confirmation per item**:

   - **Consolidation** — for each near-duplicate REX pair or overlapping error-class:
     propose ONE umbrella. REX entries are immutable (rex-format.md) → do not edit old
     entries; instead add a new consolidating entry on the most relevant tool with a
     `ref:` pointing back, or merge two error-classes in `error-classes.md` keeping both
     signatures. Never auto-apply — show the diff, ask.

   - **Telemetry** — report what triggers most/least. If a skill never fires, check its
     `keywords:` frontmatter (inject_context needs ≥2 keyword hits) — a fix here is often
     "broaden keywords", not "delete the skill".

   - **Lifecycle** — for each stale skill / cold closed error-class: propose archiving to
     `.claude/archive/` (create it if needed) OR pinning. To exempt something permanently,
     add its name (skill stem or error-class id) to `.claude/curator/pinned.txt`. Confirm
     before moving any file.

3. After any change, run `python3 .claude/scripts/validate_rex.py --strict` and
   `python3 .claude/scripts/audit_runner.py --list` to confirm nothing broke.

## Notes

- `.claude/curator/usage.json` is gitignored and seeded by `usage_telemetry` via
  `inject_context.py` (skill injections) and `audit_runner.py` (signature runs/hits).
  Early on it may be sparse — that is expected; telemetry accrues over sessions.
- This command never mutates the config on its own. The curator script is pure analysis.
- Scheduled weekly (see `.claude/curator/SCHEDULE.md`); can also be run ad-hoc.
