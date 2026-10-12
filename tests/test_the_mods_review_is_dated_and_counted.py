"""The mods study (R548) is followed by a dated, counted review — not by memory.

Type: Test
Uses: tmp_path
Depends on: tools/dev/reopen_check.py::_mods_review
Persists in: tmp_path only

Why: a study that says « on verra dans deux semaines » with nothing that comes back is
the shape this repo measured as never followed (rule 5, 0 calls in 51 sessions). The
review of the Stop gate and the statusline is a reopen condition: it counts the gate's
blocks AND its runs (0 blocks on 0 runs is a dead gate, not a quiet one), and turns
ROUVRIR on the date.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_TOOL = Path(__file__).resolve().parents[1] / "tools" / "dev" / "reopen_check.py"


@pytest.fixture
def rc(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    spec = importlib.util.spec_from_file_location("reopen_check", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _journals(d: Path) -> Path:
    blocks = [{"ts": "2026-10-20T10:00:00+00:00"}, {"ts": "2026-10-21T10:00:00+00:00"},
              {"ts": "2026-09-01T10:00:00+00:00"}]
    (d / "stop-gate.jsonl").write_text("".join(json.dumps(b) + "\n" for b in blocks))
    run = json.dumps({"hook": ".claude/hooks/require_verdict_after_edit.py"}) + "\n"
    (d / "hook-runs-20261020.jsonl").write_text(run * 5)
    (d / "hook-runs-20260901.jsonl").write_text(run * 9)
    return d


def test_before_the_date_it_waits_and_counts_the_last_14_days(rc, tmp_path) -> None:
    verdict, detail = rc._mods_review("2026-10-22", _journals(tmp_path))
    assert verdict == rc.NOT_MET
    assert "2 blocage(s)" in detail and "5 passage(s)" in detail, detail


def test_on_the_date_it_asks_for_the_review(rc, tmp_path) -> None:
    verdict, _ = rc._mods_review("2026-10-26", _journals(tmp_path))
    assert verdict == rc.MET


def test_in_ci_it_refuses_to_conclude(rc, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CI", "true")
    with pytest.raises(RuntimeError, match="n'a RIEN vérifié"):
        rc._mods_review("2026-10-26", tmp_path)


def test_the_review_is_registered(rc) -> None:
    assert any(t.evaluate is rc._mods_review for t in rc.TRIGGERS)
