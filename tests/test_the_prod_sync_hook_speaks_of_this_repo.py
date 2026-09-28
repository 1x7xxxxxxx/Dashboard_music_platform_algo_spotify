"""R310 — the prod-sync reminder fires on what reaches production HERE, and names this repo's gesture.

Type: Test
Uses: .claude/hooks/check_prod_sync.py (is_prod_affecting, main)
Persists in: nothing

Until 2026-09-28 the hook was a copy from another project: it spoke of an Industrial PC and of
Alembic revisions, and its triggers could never match this layout.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "check_prod_sync.py"


def _hook():
    spec = importlib.util.spec_from_file_location("check_prod_sync", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_it_fires_on_what_reaches_production_and_only_there() -> None:
    h = _hook()
    base = str(ROOT) + "/"
    fires = ["migrations/150_add_x.sql", "src/database/postgres_handler.py",
             "docker-compose.yml", "deploy/host/crontab", "tools/deploy.sh"]
    quiet = ["src/dashboard/views/hypeddit.py", "tests/test_x.py", "migrations/README.md"]
    assert all(h.is_prod_affecting(base + p) for p in fires), fires
    assert not any(h.is_prod_affecting(base + p) for p in quiet), quiet


def test_the_message_names_this_repos_gesture_not_another_projects() -> None:
    event = {"tool_name": "Edit", "tool_input": {"file_path": str(ROOT / "migrations" / "150_x.sql")}}
    out = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event), text=True,
                         capture_output=True)
    assert out.returncode == 0
    assert "make migrate-prod" in out.stderr and "make sync-check" in out.stderr, out.stderr
    assert "Alembic" not in out.stderr and "IPC" not in out.stderr, out.stderr
