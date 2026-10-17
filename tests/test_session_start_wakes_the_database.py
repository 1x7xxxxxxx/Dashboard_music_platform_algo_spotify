"""R640: opening a session starts the database, detached, and only the database.

guard_scope: wake_database() issues `docker start postgres_spotify_airflow` in a new session
with no pipe to wait on, and does nothing without docker. NOT covered: the stop, which is the
baseline's fleet_guard.py (2 h after the last session).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / ".claude/hooks/session_start.py"


def _hook():
    spec = importlib.util.spec_from_file_location("session_start_r640", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_session_wakes_only_the_database_detached(monkeypatch) -> None:
    mod = _hook()
    calls = []
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/docker")
    assert mod.wake_database(lambda args, **kw: calls.append((args, kw))) is True
    (args, kw), = calls
    assert args == ["/usr/bin/docker", "start", "postgres_spotify_airflow"]
    assert kw["start_new_session"] is True, "the session never waits on docker"
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert mod.wake_database(lambda *a, **k: calls.append(a)) is False and len(calls) == 1
