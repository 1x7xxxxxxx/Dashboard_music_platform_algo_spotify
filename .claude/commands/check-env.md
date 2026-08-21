---
rex:
  - date: 2026-08-21
    issue: "Described another repo: `.env` looked for in `src/Application/`, `requirements.txt` expected there too, a QuestDB :9000 probe listed unconditionally, and 'before on-site IPC deployment' as a use case. The script itself had already been made project-adaptive; this doc had not, so it described checks that no longer ran and omitted the one that does (Postgres on the port compose declares — 5433 here, not 5432)."
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
- Host clock UTC-synchronized via `timedatectl`
- **This repo's** running containers expose `TZ=UTC` — scoped to the
  `container_name:` entries compose declares, so a neighbouring project's
  containers are not reported
- Test suite collectable (`pytest --collect-only`)

Probes for services this repo does not declare (QuestDB, for one) stay silent —
`_declares()` gates them. A warning about an imaginary dependency teaches the
reader to ignore warnings.

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
