"""The write hook says when a full suite of THIS repo is running.

Type: Sub
Uses: .claude/hooks/check_python_syntax.py (`running_suite`)
Depends on: nothing — the `ps` lines and the cwd lookup are fabricated
Persists in: nothing

Class `a-verdict-from-a-tree-that-moved-under-it`: a file written while a full suite
runs is not in that suite, so its verdict describes a tree that no longer exists — twice
on 2026-09-12, 3 "failures" out of 4 did not exist. The class signature only asked
whether the warning FUNCTION exists; this file asks whether it sees the run.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "check_python_syntax.py"
_spec = importlib.util.spec_from_file_location("check_python_syntax_probe", _HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

_REPO = "/home/me/streamlytics"


def _cwd(mapping: dict):
    return lambda pid: mapping.get(pid, "")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: a full suite running in this repo is seen, with its age; a `-k`
    run, the `grep` that looks for it, and a full suite of ANOTHER repository (the
    machine-wide probe of before 2026-09-18) are not."""
    ps = ["  101    240 /usr/bin/python -m pytest tests/ -q -n 4",
          "  102     12 grep pytest tests/",
          "  103     30 python -m pytest tests/ -k smoke",
          "  104    500 python -m pytest tests/ -q"]
    cwd = _cwd({"101": _REPO, "102": _REPO, "103": _REPO,
                "104": "/home/me/knowledge-rag"})
    assert hook.running_suite(ps, cwd, _REPO) == ("101", 240)
    assert hook.running_suite([ps[1], ps[2]], cwd, _REPO) is None
    assert hook.running_suite([ps[3]], cwd, _REPO) is None
