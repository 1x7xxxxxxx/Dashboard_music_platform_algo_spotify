"""R562 — a refusal replayed under session "probe" is not counted as a second gesture.

Type: Test
Uses: tools/dev/defect_log.py::refusals
Depends on: nothing live
Persists in: nothing

Measured 2026-10-14: 35 refusals logged under session "probe" on 2026-10-07/08, each a
copy of a real one, doubled the "REFUS 7 j" line of night-status for those days.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "dev"))

import defect_log  # noqa: E402


def _refusal(session: str) -> dict:
    return {"kind": "hook_refusal", "fingerprint": "roadmap", "ts": "2026-10-07T09:00:00Z",
            "session": session}


def test_a_probe_copy_does_not_double_the_count() -> None:
    rows = defect_log.refusals([_refusal("abc"), _refusal("probe")])
    assert rows == [("roadmap", 1, ["2026-10-07"])]


def test_two_real_refusals_still_count_two() -> None:
    assert defect_log.refusals([_refusal("abc"), _refusal("def")])[0][1] == 2
