"""The R282 proposals compute what their titles claim (tools/dev/charts_dossier/proposals.py).

A proposal is judged by the owner on its picture; the calculations under the pictures are
pinned here on series whose answer is known by construction. The lag, CTA, fatigue and
playlist proposals were refused by the owner on 2026-09-28 and removed with their tests;
P2 lives in the app (R291, tests/test_a_campaign_wave_is_judged_as_one.py).

Does not cover: the SQL (it runs on the review snapshot only), nor the drawing — the PNGs are
looked at before the dossier is sent.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "dev" / "charts_dossier"))

import proposals  # noqa: E402

_DAYS = pd.date_range("2024-01-01", periods=120, freq="D")


def test_the_curve_is_indexed_on_the_28_days_before_each_wave():
    streams = pd.Series(50.0, index=_DAYS)
    streams.loc["2024-03-01":"2024-03-10"] = 150.0
    es = proposals.event_study(streams, [("A", dt.date(2024, 3, 1))])
    at = es.set_index("offset")["index"]
    assert at[-1] == 100.0 and at[0] == 300.0 and at[10] == 100.0


def test_a_wave_with_almost_no_streams_before_it_is_left_out():
    """The first wave of artist 1 began before its first release: « indice 1 332 800 »."""
    streams = pd.Series(0.2, index=_DAYS)
    streams.loc["2024-03-01":] = 300.0
    assert proposals.event_study(streams, [("A", dt.date(2024, 3, 1))]).empty


def test_streams_per_click_is_none_when_nothing_was_gained():
    assert proposals.streams_per_click(500.0, 250.0) == 2.0
    assert proposals.streams_per_click(None, 250.0) is None
    assert proposals.streams_per_click(-10.0, 250.0) is None
