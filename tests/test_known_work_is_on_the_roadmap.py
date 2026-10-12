"""R532 — an open defect or an unanswered `recurrence:` billet must be named by a roadmap row.

Type: Test
Uses: tools/dev/night_run.py (unrouted_work, defect_needle)
Persists in: nothing

2026-10-12: the roadmap was announced empty while `night-status` showed two open
defects and a pending billet on an info line. `night-check` now refuses that.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "dev"))
import night_run  # noqa: E402

_FP = "test:tests/test_the_monitor_itself_still_runs.py::test_the_daily_probe_ran"
_OPEN = {"status": "open", "fingerprint": _FP, "recurrence_proposal": None, "ticket": None}


def _row(text: str) -> list[tuple[str, str, str]]:
    return [("R900", text, "P3")]


def test_an_open_defect_no_row_names_is_refused():
    out = night_run.unrouted_work([_OPEN], _row("autre chose"))
    assert len(out) == 1 and "test_the_monitor_itself_still_runs.py" in out[0]


def test_a_row_naming_its_test_file_carries_it():
    assert night_run.unrouted_work(
        [_OPEN], _row("`tests/test_the_monitor_itself_still_runs.py` rougit sur un 502")) == []


def test_a_pending_billet_is_work_and_an_answered_one_is_not():
    billet = {"status": "green", "fingerprint": "ci-step:Portes statiques/REX integrity",
              "recurrence_proposal": "recurrence:2026-10-04,2026-10-10", "ticket": None}
    assert night_run.unrouted_work([billet], []) != []
    assert night_run.unrouted_work([{**billet, "ticket": {"verdict": "distinct"}}], []) == []


def test_a_green_defect_is_not_work():
    assert night_run.unrouted_work([{**_OPEN, "status": "green"}], []) == []


def test_the_needle_of_a_ci_step_is_its_step():
    assert night_run.defect_needle("ci-step:Portes statiques/REX integrity") == "REX integrity"
