---
rex:
  - date: 2026-08-21
    issue: "Described another repo: `.env` and `requirements.txt` looked for under `src/Application/`, a QuestDB :9000 probe listed unconditionally, and on-site IPC deployment as a use case. It omitted the check that does run — Postgres on the port compose declares, 5433 here."
    fix: "Rewrote the check list from the script's actual output, including the DB-gate consequence: with Postgres down, 128 tests skip silently, so a green suite means less than it looks."
    ref: "R36"
    severity: warn
---

Run the environment prerequisite check for this repo.

## What to do

```bash
python3 .claude/scripts/check_env.py
```

or `make check-env`.

The script checks:

- Python ≥ 3.10
- `ruff` available (linting — CI blocks on `ruff check src/ tests/`)
- `pytest` available
- `.env` present at the repo root
- `requirements.txt` present
- Docker daemon reachable
- **PostgreSQL on the port this repo's compose declares** — 5433 here, read from
  `docker-compose.yml`, not assumed
- Host clock **NTP-synchronised** via `timedatectl` — drift, not zone. Stripe
  rejects a webhook signature outside a five-minute window and JWT expiry has no
  tolerance; whether your laptop reads CEST or UTC changes nothing
- **This repo's** containers **agree on a TZ** — scoped to the `container_name:`
  entries compose declares, so a neighbouring project's containers are not
  reported. All five services declare `TZ: Europe/Paris` on purpose, and Airflow
  runs `core.default_timezone = utc`, so a probe demanding `TZ=UTC` would be
  asking to break a deliberate choice. Disagreement between containers is the
  real defect — two log streams that cannot be lined up
- Test suite collectable (`pytest --collect-only`)

Probes for services this repo does not declare (QuestDB, for one) stay silent —
`_declares()` gates them. A warning about an imaginary dependency teaches the
reader to ignore warnings, and so does a check that demands a value the project
never chose: the two TZ checks above each did exactly that until 2026-08-21, and
between them accounted for both false positives in a 7/10 score. It reads 9/10
now, and the one remaining warning is a real blocker (R18).

## After running

If a check fails, suggest the exact fix shown in the ❌ / ⚠️ line.

One consequence is worth stating out loud when Postgres is down: about **128
tests are DB-gated** (`tests/db_gate.py`) and skip silently. A green suite with
`PostgreSQL :5433` unreachable is a weaker result than the same numbers with it
up — say which one was run.

## When to use

- At session start when the environment feels broken
- After `git clone` on a new machine
- Before claiming a test run is complete (see the `verification` skill, Phase 2)
- When tests fail unexpectedly — rule out the environment first
