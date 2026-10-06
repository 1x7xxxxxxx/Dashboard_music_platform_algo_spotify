# Curator schedule

`/curator` is meant to run **weekly** so the config keeps consolidating and shedding
dead weight (the hermes "improves each iteration" property). It is report-only, so a
scheduled run never changes anything on its own — it produces a report you triage.

## How it's scheduled

`make night-status` — which every `/resume` runs — reruns `curator.py` when
`last-run` is older than 7 days and writes the report to `.claude/curator/last-report.md`
(R417, 2026-10-06). Before that, the Stop hook asked for `/curator` at the end of every
turn once the week had passed: 48 sessions, 0 runs. A reminder nobody follows is noise;
a run that happens on the path already taken is not.

`/curator` stays available by hand for an off-cycle pass.

## Why not a system crontab

`curator.py` only reads repo files + the local `usage.json` sidecar and emits a
markdown report a human must act on — there is no value in running it headless on a
server (no one would read the output, and it proposes edits that need validation).
Keep system crontabs for things that must act unattended (backups, schema-drift mail).

## Seeding telemetry

`usage.json` is gitignored and starts empty. It fills as:
- `inject_context.py` injects a skill (≥2 keyword hits in a prompt) → `skills` counter,
- `audit_runner.py` runs a signature (`make audit` / CI nightly) → `error_classes` runs/hits.

Until it has a few weeks of data, the telemetry + lifecycle sections will be sparse —
that is expected, not a bug.
