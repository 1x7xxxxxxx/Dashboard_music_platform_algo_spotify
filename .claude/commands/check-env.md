---
rex: []
---

Run the  environment prerequisite check.

## What to do

Run the check script and report results to the user:

```bash
python3 .claude/scripts/check_env.py
```

The script checks:
- Python ≥ 3.10
- ruff available (linting)
- pytest available (test runner)
- .env file present (repo root or )
- requirements.txt present in 
- Docker daemon reachable
- <your time-series DB> port 9000 reachable (optional — warn if not)
- Host clock UTC-synchronized via `timedatectl` (brick sync-phase-0, Linux/IPC only)
- Running containers expose `TZ=UTC` env (brick sync-phase-0)
- Test suite collectable (pytest --collect-only)

## After running

If any check fails, suggest the specific fix shown in the ❌ line.
If all pass, confirm environment is ready for development.

## When to use

- At session start when environment feels broken
- After git clone on a new machine
- Before on-site IPC deployment (run from IPC to verify setup)
- When tests fail unexpectedly (rule out environment issues first)
