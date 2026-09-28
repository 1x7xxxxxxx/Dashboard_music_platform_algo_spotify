"""R297 (R293) — the model's error is read per WEEK the prediction was made, gated like
the volume it measures.

Type: Test
Uses: pytest, pandas, streamlit.testing.v1.AppTest
Depends on: src/dashboard/views/trigger_algo/_tab_model.py (error_by_prediction_week,
            _show_error_by_prediction_week), src/dashboard/utils/algo_knowledge.py
Persists in: nothing

Fiche 51 compares the LATEST prediction of each title with its S4A reading: one point.
The owner asked (2026-09-28) for the trend the corpus recommends (Crowe et al., p. 322):
every prediction made before the reading, grouped by the week it was made. Measured on
the prod snapshot the same day: Radio's median gap is 9 streams in the week of 8 June
and 7 in every week after — the model barely changes its mind.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.dashboard.utils import algo_knowledge as ak
from src.dashboard.views.trigger_algo._tab_model import error_by_prediction_week


def _rows() -> pd.DataFrame:
    # Two weeks; song "a" predicted twice in week 1. Reading: 10 Radio streams for both.
    return pd.DataFrame({
        "prediction_date": ["2026-09-01", "2026-09-02", "2026-09-01", "2026-09-08"],
        "song": ["a", "a", "b", "a"],
        "recorded_at": ["2026-09-20"] * 4,
        "radio_streams": [10.0, 10.0, 10.0, 10.0],
        "predicted_radio": [30.0, 20.0, 14.0, 12.0],
        "dw_streams": [1.0] * 4, "predicted_dw": [None] * 4,
        "rr_streams": [1.0] * 4, "predicted_rr": [0.0] * 4,
    })


def test_each_week_is_the_median_gap_of_the_forecasts_made_that_week() -> None:
    got = error_by_prediction_week(_rows(), "RADIO")
    assert list(got["error"]) == [10.0, 2.0], got      # week 1: |20|,|10|,|4| → 10
    assert list(got["titles"]) == [2, 1], got
    assert got["week"].is_monotonic_increasing


def test_a_signed_gap_would_cancel_out_and_is_not_what_is_drawn() -> None:
    rows = _rows().assign(predicted_radio=[0.0, 20.0, 10.0, 10.0])   # −10, +10, 0
    assert error_by_prediction_week(rows, "RADIO")["error"].iloc[0] == 10.0


def test_an_algorithm_without_forecasts_yields_no_series() -> None:
    assert error_by_prediction_week(_rows(), "DW").empty


def _script() -> None:
    from src.dashboard.views.trigger_algo._tab_model import _show_error_by_prediction_week
    from tests.test_the_model_error_is_read_per_prediction_week import _rows

    class _FakeDB:
        def fetch_df(self, _query, _params=None):
            return _rows()

    _show_error_by_prediction_week(_FakeDB(), 999)


def _drawn(at: AppTest) -> list[str]:
    return [tr.get("name") for el in at.get("plotly_chart")
            for tr in json.loads(el.proto.spec).get("data", [])]


def test_only_the_algorithms_whose_volume_is_shown_are_drawn() -> None:
    at = AppTest.from_function(_script, default_timeout=30)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    shown = {"Radio"} if ak.volume_forecast_reliable("RADIO") else set()
    assert set(_drawn(at)) == shown, _drawn(at)
    assert any("1 relevé(s) S4A" in c.value for c in at.caption), [c.value for c in at.caption]


def test_a_suppressed_volume_has_no_weekly_error_either(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(ak.ALGO_REGRESSOR_METRICS, "RADIO",
                        dict(ak.ALGO_REGRESSOR_METRICS["RADIO"], volume_reliable=False))
    at = AppTest.from_function(_script, default_timeout=30)
    at.run()
    assert not at.exception and _drawn(at) == [], _drawn(at)
