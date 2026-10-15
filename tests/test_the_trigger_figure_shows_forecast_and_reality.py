"""R560 — one figure answers « what does a trigger bring, and what did MY title do ».

Owner's notes of 2026-10-13, fiches 129 and 48: the forecast table and the lifecycle
cohort were two answers to one question. R583 (2026-10-15) moved the figure beside each
playlist's gauges — its drawing is tested in test_a_release_target_says_where_it_comes_from. They are one figure now: per algorithm, in
trigger order (RR → DW → Radio, ADR-033 §3), the dotted median of triggered titles over
its P25–P75 band, and the title's own 28-day readings as solid points at their age.
"""
import pandas as pd

from src.dashboard.views.trigger_algo import _tab_algo_streams as m

_EST = {"estimates": {
    "dw": {"j28": {"p25": 200, "p50": 585, "p75": 1400, "n": 40},
           "m6": {"p25": 400, "p50": 878, "p75": 3100, "n": 12}, "y1": {"n": 8, "refused": True}},
    "rr": {"j28": {"p25": 200, "p50": 546, "p75": 1150, "n": 30},
           "m6": {"n": 0, "refused": True}, "y1": {"n": 0, "refused": True}},
    "radio": {"j28": {"p25": 900, "p50": 1584, "p75": 3000, "n": 20},
              "m6": {"p25": 1700, "p50": 4727, "p75": 22500, "n": 11},
              "y1": {"n": 9, "refused": True}}}}


def test_release_radar_comes_first():
    assert m.TRIGGER_ORDER == ("RR", "DW", "RADIO")


def test_a_reading_is_placed_at_its_age_and_never_before_release():
    df = pd.DataFrame({"recorded_at": ["2026-01-28", "2026-07-06", "2025-12-01"],
                       "dw_streams": [420, 0, 1], "radio_streams": [900, 3100, 1],
                       "rr_streams": [700, 0, 99]})
    out = m.readings_by_age(df, pd.Timestamp("2026-01-01"))
    assert out["age_days"].tolist() == [27, 186]
    assert 99 not in out["RR"].tolist()


def test_the_last_age_shown_is_the_last_with_something_to_draw():
    """R570 — a refused age past every reading is not drawn; a later reading widens it."""
    assert m.x_max(_EST["estimates"], []) == 182
    late = pd.DataFrame({"age_days": [300], "DW": [1.0], "RADIO": [1.0], "RR": [1.0]})
    assert m.x_max(_EST["estimates"], [late]) == 300
