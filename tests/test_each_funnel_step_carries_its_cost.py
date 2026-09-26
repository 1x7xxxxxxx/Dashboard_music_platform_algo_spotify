"""Each step of « Tout mon funnel » carries its cost, and « streams gained » needs a baseline.

Type: Test
Uses: src.dashboard.views.meta_x_spotify (_step_texts, _streams_gained)
Depends on: nothing — pure functions
Persists in: nothing

R213 (lot b, 2026-09-27). The owner asked to optimise Meta over the WHOLE funnel: every step
now says what one unit of it cost (spend ÷ volume) and what share of the previous step it
kept. The last step, « streams gained », is the linked track's streams above its
pre-campaign level — and it must be ABSENT, never 0, when that level is not measured.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from src.dashboard.views.meta_x_spotify import (
    _BASELINE_MIN_DAYS, _step_texts, _streams_gained,
)


def test_each_step_is_priced_as_spend_over_its_volume() -> None:
    texts = _step_texts([10_000, 200, 100], spend=50.0)
    assert "5,000 € les 1 000" in texts[0], texts[0]           # 50 / 10 000 × 1000
    assert "0,250 € l'unité" in texts[1] and "2,0 %" in texts[1], texts[1]
    assert "0,500 € l'unité" in texts[2] and "50,0 %" in texts[2], texts[2]


def test_no_spend_means_no_cost_rather_than_a_zero_cost() -> None:
    assert not any("€" in x for x in _step_texts([1000, 10], spend=None))


def _daily(before_days: int, before: float, during_days: int, during: float, d0):
    rows = [(d0 - dt.timedelta(days=i + 1), before) for i in range(before_days)]
    rows += [(d0 + dt.timedelta(days=i), during) for i in range(during_days)]
    return pd.DataFrame(rows, columns=["date", "streams"])


def test_streams_gained_is_the_rise_above_the_pre_campaign_level() -> None:
    d0 = dt.date(2024, 5, 1)
    got = _streams_gained(_daily(20, 10, 5, 30, d0), d0, d0 + dt.timedelta(days=4))
    assert got and got["gained"] == 100 and got["baseline_per_day"] == 10, got


def test_a_short_baseline_gives_no_step_not_a_zero() -> None:
    d0 = dt.date(2024, 5, 1)
    short = _daily(_BASELINE_MIN_DAYS - 1, 10, 5, 30, d0)
    assert _streams_gained(short, d0, d0 + dt.timedelta(days=4)) is None
    assert _streams_gained(pd.DataFrame(columns=["date", "streams"]), d0, d0) is None
