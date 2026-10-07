"""R446 — every red test of main's CI is filed under the road it took past the local gate.

Type: Sub
Uses: tools/dev/ci_red_escape.py (reds_by_run, previous_green, escape)
Depends on: nothing — runs and selections are fabricated

The remedies are opposite: a selector miss means fixing `select_tests.py` (R447 was found
this way), an unstamped push is what R444 now refuses, and a red that passed both is an
environment difference to name. Mixing them loses all three signals.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "ci_red_escape", Path(__file__).resolve().parents[1] / "tools/dev/ci_red_escape.py")
esc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(esc)

NODE = "test:tests/test_a.py::test_x"


def test_a_test_the_selector_would_not_run_is_a_selector_miss():
    picked = {"all": False, "paths": ["tests/test_b.py"]}
    assert esc.escape(NODE, picked, gated=True) == "selector-miss"
    assert esc.escape(NODE, picked, gated=False) == "selector-miss"


def test_a_selected_test_splits_on_the_pre_push_gate():
    picked = {"all": False, "paths": ["tests/test_a.py"]}
    assert esc.escape(NODE, picked, gated=False) == "unstamped-push"
    assert esc.escape(NODE, picked, gated=True) == "local-vs-ci"
    assert esc.escape(NODE, {"all": True, "paths": []}, gated=True) == "local-vs-ci"


def test_a_failed_step_without_a_node_is_outside_the_selector():
    assert esc.escape("ci-step:Portes/REX", {"all": False, "paths": []}, True) == "ci-step"


def test_the_escaping_diff_starts_at_the_last_green_before_the_red():
    runs = [  # newest first, as `gh run list` returns them
        {"databaseId": 5, "conclusion": "failure", "headSha": "e"},
        {"databaseId": 4, "conclusion": "success", "headSha": "d"},
        {"databaseId": 3, "conclusion": "failure", "headSha": "c"},
        {"databaseId": 2, "conclusion": "cancelled", "headSha": "b"},
        {"databaseId": 1, "conclusion": "success", "headSha": "a"},
    ]
    assert esc.previous_green(runs, "5") == "d"
    assert esc.previous_green(runs, "3") == "a"     # a cancelled run is no verdict
    assert esc.previous_green(runs, "1") is None


def test_only_ci_reds_are_read_from_the_defect_log():
    events = [
        {"source": "ci", "kind": "test_red", "fingerprint": NODE, "session": "ci:9"},
        {"source": "ci", "kind": "test_red", "fingerprint": NODE, "session": "ci:9"},
        {"source": "ci", "kind": "test_green", "fingerprint": "green", "session": "ci:8"},
        {"kind": "test_red", "fingerprint": NODE, "session": "abc"},
    ]
    assert esc.reds_by_run(events) == {"9": [NODE]}
    assert all(road in esc.ADVICE for road in
               ("selector-miss", "unstamped-push", "local-vs-ci", "ci-step"))


def test_the_defect_log_runs_the_classifier_after_importing_the_reds():
    make = (Path(__file__).resolve().parents[1] / "Makefile").read_text()
    body = make.split("\ndefect-log:", 1)[1].split("\n\n", 1)[0]
    cmds = [ln.strip().lstrip("@").split("#", 1)[0].strip() for ln in body.splitlines()[1:]]
    assert "python3 tools/dev/ci_red_escape.py" in cmds
    assert cmds.index("python3 tools/dev/import_ci_reds.py") < cmds.index(
        "python3 tools/dev/ci_red_escape.py")
