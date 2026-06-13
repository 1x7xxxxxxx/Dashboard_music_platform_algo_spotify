# Curator schedule

`/curator` is meant to run **weekly** so the config keeps consolidating and shedding
dead weight (the hermes "improves each iteration" property). It is report-only, so a
scheduled run never changes anything on its own — it produces a report you triage.

## How it's scheduled

The curator is **self-paced via Claude Code**, not a system cron (unlike the prod
`schema_drift_cron.sh`, which must run on the server). Two equivalent triggers:

- **Ad-hoc**: run `/curator` any time (e.g. at the end of a heavy config session).
- **Recurring**: ask Claude to `/schedule` a weekly `/curator` run, or add a calendar
  reminder. A weekly cadence matches how fast REX/error-classes accumulate here.

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
