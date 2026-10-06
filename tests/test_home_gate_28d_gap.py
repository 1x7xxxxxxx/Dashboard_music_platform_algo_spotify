"""R424 — each home gate says the streams left over 28 days and their price at the best CPR.

Type: Test
Uses: src/dashboard/views/home_tiles.py (gate_gaps_28d, _gate_sub)
Depends on: src/dashboard/utils/algo_knowledge.py (the model's trigger zones)
Persists in: nothing

The owner, 2026-10-06: « le nombre de streams restant à faire sur les 28 prochains jours
et le budget associé en fonction du meilleur CPR ». Targets: DW and Radio from the model's
non-algo 28-day zone, RR's 7-day threshold ×4 (the owner's choice). Price: gap × best CPR,
read as one click = one stream.
"""
from __future__ import annotations

import math

from src.dashboard.utils.algo_knowledge import ALGO_FEATURE_ZONES
from src.dashboard.views.home_tiles import _gate_sub, gate_gaps_28d


def _target(algo: str, fid: str) -> float:
    return ALGO_FEATURE_ZONES[algo][fid]["target"]


def test_each_gate_measures_its_gap_against_the_models_28_day_target() -> None:
    nonalgo = 108
    gaps = gate_gaps_28d(math.log1p(nonalgo), 500)
    assert gaps == {
        "release_dw": round(_target("DW", "NonAlgoStreams28Days") - nonalgo),
        "release_radio": round(_target("RADIO", "NonAlgoStreams28Days") - nonalgo),
        "release_rr": round(4 * _target("RR", "StreamsLast7Days") - 500),
    }


def test_a_met_target_is_zero_never_negative() -> None:
    gaps = gate_gaps_28d(math.log1p(50_000), 50_000)
    assert set(gaps.values()) == {0}
    assert "✅" in _gate_sub(0, 0.11)


def test_an_unknown_measure_is_left_out_not_shown_as_the_whole_target() -> None:
    gaps = gate_gaps_28d(None, None)
    assert "release_dw" not in gaps and "release_radio" not in gaps
    assert _gate_sub(gaps.get("release_dw"), 0.11) == ""


def test_the_budget_is_the_gap_at_the_best_cpr() -> None:
    line = _gate_sub(2000, 0.109)
    assert "2 000" in line and "218 €" in line
    assert "€" not in _gate_sub(2000, None), "no CPR → no invented price"


# R426 — « c'est que sur les 28 premiers jours de la sortie » (the owner, 2026-10-06).

def test_release_radar_window_is_the_releases_first_28_days() -> None:
    from src.dashboard.views.home_tiles import rr_days_left
    assert rr_days_left(0) == 28 and rr_days_left(27) == 1
    assert rr_days_left(28) == 0 and rr_days_left(766) == 0
    assert rr_days_left(None) is None


def test_a_shut_window_shows_no_budget() -> None:
    line = _gate_sub(8000, 0.22, days_left=0)
    assert "€" not in line and "8\u202f000" not in line
    assert line != _gate_sub(8000, 0.22)


def test_an_open_window_names_the_days_left_and_the_price() -> None:
    line = _gate_sub(5000, 0.2, days_left=10)
    assert "5\u202f000" in line and "10 j" in line and "1\u202f000\u00a0€" in line
