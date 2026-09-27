"""Closing a roadmap task also closes its night-run unit (R225, 2026-09-27).

Type: Test
Uses: tools/dev/roadmap.py::close_night_unit
Depends on: nothing — a temporary journal
Persists in: nothing

Three units (R213, R215, R218) stayed open after their task was archived, one night;
`night-check` ended red. Two gestures that must happen together are one gesture.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _roadmap():
    spec = importlib.util.spec_from_file_location("roadmap_tool", ROOT / "tools/dev/roadmap.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _journal(tmp_path, *records) -> Path:
    p = tmp_path / "night-run.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return p


def _kinds(p: Path) -> list[tuple[str, str]]:
    return [(r["kind"], r["task"]) for r in map(json.loads, p.read_text().splitlines())]


def test_an_open_unit_of_the_task_is_closed(tmp_path) -> None:
    p = _journal(tmp_path, {"kind": "start", "task": "R900", "what": "x"})
    assert _roadmap().close_night_unit("R900", "livré", journal=p) is True
    assert _kinds(p)[-1] == ("done", "R900")


def test_another_task_or_a_closed_unit_is_left_alone(tmp_path) -> None:
    p = _journal(tmp_path, {"kind": "start", "task": "R900", "what": "x"},
                 {"kind": "done", "task": "R900", "what": "y"},
                 {"kind": "start", "task": "R901", "what": "z"})
    assert _roadmap().close_night_unit("R900", "", journal=p) is False
    assert _kinds(p)[-1] == ("start", "R901"), "R901's open unit must stay open"
