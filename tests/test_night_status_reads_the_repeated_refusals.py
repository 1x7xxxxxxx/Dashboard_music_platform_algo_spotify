"""R453 — `night-status` prints the most repeated refusals of the last seven days.

Type: Test
Uses: tools/dev/night_run.py (recent_refusals), tools/dev/defect_log.py (refusals)
Depends on: nothing — events are fabricated

The table « Refus répétés » existed since R315 and was read only by a hand-run
`make defect-log`: what nothing reads does not act. A guard that starts refusing twenty
times a day must show on waking up.

Mutation record (2026-10-07): the window filter removed → red (the old refusal outranks);
`[:top]` removed → red (four labels printed).
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

_DEV = Path(__file__).resolve().parents[1] / "tools" / "dev"
sys.path.insert(0, str(_DEV))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"_r453_{name}", _DEV / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


night = _load("night_run")
defect_log = _load("defect_log")


def _ev(fp: str, day: str, kind: str = "precommit_refusal") -> dict:
    return {"kind": kind, "fingerprint": fp, "ts": f"{day}T10:00:00+00:00"}


DURATIONS = "precommit:tests — every staged test has a recorded duration (make test-durations-missing)"


def test_the_week_is_ranked_and_cut_to_three():
    events = ([_ev(DURATIONS, "2026-10-06")] * 4
              + [_ev("precommit:roadmap — cites an open Rnnn", "2026-10-05")] * 3
              + [_ev("hook:guard_destructive:verdict tube", "2026-10-04", "hook_refusal")] * 2
              + [_ev("precommit:end-of-file", "2026-10-03")]
              + [_ev("precommit:old — last month", "2026-09-20")] * 9
              + [_ev("test:x", "2026-10-06", "test_red")] * 9)
    line = night.recent_refusals(events, "2026-10-07", defect_log.refusals)
    assert line == ("▶ REFUS 7 j  test-durations-missing ×4 · roadmap ×3 · "
                    "guard_destructive:verdict tube ×2")


def test_a_quiet_week_prints_nothing():
    old = [_ev(DURATIONS, "2026-09-30")] * 5   # exactly 7 days back: outside
    assert night.recent_refusals(old, "2026-10-07", defect_log.refusals) is None


def _calls_in_status() -> set[str]:
    tree = ast.parse((_DEV / "night_run.py").read_text(encoding="utf-8"))
    status = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "cmd_status")
    return {n.func.id for n in ast.walk(status)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


def test_status_calls_the_refusal_line():
    assert "recent_refusals" in _calls_in_status()
