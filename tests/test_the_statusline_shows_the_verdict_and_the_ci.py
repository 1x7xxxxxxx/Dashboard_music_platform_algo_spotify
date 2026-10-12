"""The statusline never shows a green it did not read (R550).

Type: Test
Uses: tmp_path, monkeypatch
Depends on: .claude/scripts/statusline.py, .claude/hooks/_verdict.py
Persists in: tmp_path only

Why: the HUD of a session is read at a glance, so a wrong glyph is believed. Two
failures it must not have: an unknown CI drawn as ✅ (this repo's most paid defect — a
full table reads as fresh), and a verdict older than the last edit drawn as green. And
it must never block on the network: Claude Code redraws it at every message.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / ".claude" / "scripts" / "statusline.py"


@pytest.fixture
def sl(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("statusline", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "statusline", mod)  # @dataclass resolves its module
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "CACHE", tmp_path / "cache")
    return mod


_PAYLOAD = {"model": {"display_name": "Opus"}, "context_window": {"used_percentage": 42.3},
            "cost": {"total_cost_usd": 3.217, "total_duration_ms": 5_400_000,
                     "total_lines_added": 310, "total_lines_removed": 12}}


def _state(sl, state="vert", ci=None, **kw):
    v = sl.Verdict(state, passed=12, failed=2 if state == "rouge" else 0, edited_file="src/a.py")
    return sl.State(tests=v, ci=ci, sha="0123456789abcdef", dirty=1, ahead=2, **kw)


def test_the_first_line_is_the_session(sl) -> None:
    line1, _ = sl.render(_PAYLOAD, _state(sl))
    assert line1 == "Opus · ctx 42 % · ~$3.22 · 1h30 · +310/−12"


def test_an_unknown_ci_is_a_question_mark_never_green(sl) -> None:
    _, line2 = sl.render(_PAYLOAD, _state(sl, ci=None))
    assert "CI ? 01234567" in line2 and "✅" not in line2.split("CI")[1]


@pytest.mark.parametrize("ci,glyph", [("success", "✅"), ("failure", "❌"),
                                      ("running", "⏳"), ("none", "aucun run")])
def test_a_known_ci_has_its_glyph(sl, ci, glyph) -> None:
    assert f"CI {glyph}" in sl.render(_PAYLOAD, _state(sl, ci=ci))[1]


@pytest.mark.parametrize("state,shown", [("vert", "✅ 12 verts"), ("rouge", "❌ 2 rouge(s)"),
                                         ("en cours", "⏳"), ("périmé", "⚠️ périmé (a.py)"),
                                         ("absent", "aucun verdict")])
def test_the_test_verdict_is_drawn_from_its_state(sl, state, shown) -> None:
    line2 = sl.render(_PAYLOAD, _state(sl, state))[1]
    assert shown in line2
    if state != "vert":
        assert "✅" not in line2.split("·")[0]


def test_one_red_run_makes_the_ci_red(sl) -> None:
    runs = [{"status": "completed", "conclusion": "success"},
            {"status": "completed", "conclusion": "failure"}]
    assert sl.ci_from_runs(runs) == "failure"
    assert sl.ci_from_runs([{"status": "in_progress", "conclusion": ""}]) == "running"
    assert sl.ci_from_runs([]) == "none"


def test_the_ci_is_never_fetched_synchronously(sl, monkeypatch) -> None:
    started: list = []

    class _Popen:
        def __init__(self, argv, **kw):
            started.append((argv, kw))

    def _no_run(*a, **k):
        raise AssertionError("a synchronous subprocess in the CI path blocks the redraw")

    monkeypatch.setattr(sl.subprocess, "Popen", _Popen)
    monkeypatch.setattr(sl.subprocess, "run", _no_run)
    assert sl._ci_state(Path("."), "abc") is None, "no cache yet: unknown, not green"
    assert started and started[0][1].get("start_new_session") is True
    assert sl._ci_state(Path("."), "abc") is None and len(started) == 1, "refreshed twice in a TTL"


def test_a_final_cached_ci_is_not_refetched(sl, monkeypatch) -> None:
    sl.CACHE.mkdir()
    (sl.CACHE / "streamlytics-ci-abc.json").write_text(
        json.dumps([{"status": "completed", "conclusion": "success"}]))
    monkeypatch.setattr(sl.subprocess, "Popen", lambda *a, **k: pytest.fail("refetched"))
    assert sl._ci_state(Path("."), "abc") == "success"


def test_the_script_answers_fast_and_in_two_lines(tmp_path) -> None:
    import subprocess
    payload = dict(_PAYLOAD, workspace={"project_dir": str(tmp_path)})
    t = time.monotonic()
    r = subprocess.run([sys.executable, str(_SCRIPT)], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=10)
    assert r.returncode == 0 and len(r.stdout.splitlines()) == 2, r.stdout + r.stderr
    assert time.monotonic() - t < 2.0
