"""Each step of « Tout mon funnel » carries its cost, and « streams gained » needs a baseline.

Type: Test
Uses: src.dashboard.utils.campaign_funnel, src.dashboard.views.meta_x_spotify (_collect_apple)
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

from src.dashboard.utils.campaign_funnel import (
    BASELINE_MIN_DAYS as _BASELINE_MIN_DAYS, engagement_lift as _engagement_lift_fn,
    step_texts as _step_texts, streams_gained as _streams_gained,
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


# ── Apple / Shazam around the campaign (R213 lot e) ───────────────────────────
class _Db:
    def __init__(self, rows):
        self.rows = rows

    def fetch_df(self, sql, params=None):
        return pd.DataFrame(self.rows, columns=["date", "apple_plays", "apple_shazams",
                                                "days_since_previous"])


def _apple(rows, d0=dt.date(2024, 6, 1), d1=dt.date(2024, 6, 30)):
    from src.dashboard.views.meta_x_spotify import _collect_apple
    frames, absences = [], []
    _collect_apple(_Db(rows), 1, "Song", d0, d1, frames, absences)
    return frames, absences


def test_daily_apple_readings_enter_the_figure() -> None:
    frames, absences = _apple([(dt.date(2024, 6, 2), 5, 1, 1), (dt.date(2024, 6, 3), 7, 2, 1)])
    assert absences == [] and len(frames[0]) == 2


def test_readings_after_the_window_say_when_they_start_not_that_there_are_none() -> None:
    """Seen on the render 2026-09-27: filtering on the window end in SQL said « no reading »."""
    _, absences = _apple([(dt.date(2025, 11, 29), None, None, None)])
    assert absences == [("apple_late", dt.date(2025, 11, 29))], absences


def test_sparse_readings_are_not_drawn_as_daily() -> None:
    frames, absences = _apple([(dt.date(2024, 6, 10), 50, 4, 40)])
    assert frames == [] and absences == [("apple_sparse", None)]


def test_no_reading_at_all_is_said() -> None:
    assert _apple([])[1] == [("apple_none", None)]


# ── Engagement beyond streams (R213 lot d) ────────────────────────────────────
def test_a_flow_compares_means_and_a_level_compares_gains() -> None:
    _engagement_lift = _engagement_lift_fn
    d0 = dt.date(2024, 5, 1)
    rows = [(d0 - dt.timedelta(days=i + 1), 10, 1000 - i) for i in range(20)]      # +1/day
    rows += [(d0 + dt.timedelta(days=i), 20, 1000 + 3 * i) for i in range(5)]        # +3/day
    df = pd.DataFrame(rows, columns=["date", "saves", "followers_level"])
    got = {r["col"]: r for r in _engagement_lift(df, d0, d0 + dt.timedelta(days=4))}
    assert got["saves"]["before"] == 10 and got["saves"]["during"] == 20
    assert got["saves"]["change"] == 100
    assert got["followers_level"]["before"] == 1 and got["followers_level"]["during"] == 3


def test_an_unmeasured_baseline_is_absent_not_zero() -> None:
    _engagement_lift = _engagement_lift_fn
    d0 = dt.date(2024, 5, 1)
    rows = [(d0 + dt.timedelta(days=i), 20, None) for i in range(5)]
    got = _engagement_lift(pd.DataFrame(rows, columns=["date", "saves", "ig_followers"]),
                           d0, d0 + dt.timedelta(days=4))
    assert all(r["before"] is None and r["change"] is None for r in got), got
    assert next(r for r in got if r["col"] == "ig_followers")["during"] is None


# ── Shazam → streams, with its delay (R235) ──────────────────────────────────
def test_the_shazam_lag_is_found_where_the_data_puts_it() -> None:
    from src.dashboard.utils.campaign_funnel import shazam_stream_lag
    import numpy as np
    days = pd.date_range("2026-05-01", periods=30, freq="D")
    rng = np.random.default_rng(7)
    shazams = pd.Series(rng.integers(0, 50, 30), index=days, dtype=float)
    streams = shazams.shift(2).fillna(0) * 10          # streams follow Shazams by 2 days
    master = pd.DataFrame({"date": days, "apple_shazams": shazams.values,
                           "streams": streams.values})
    got = shazam_stream_lag(master)
    assert got and got["lag"] == 2 and got["corr"] > 0.9, got


def test_too_few_paired_days_give_no_number() -> None:
    from src.dashboard.utils.campaign_funnel import MIN_PAIRED_DAYS, shazam_stream_lag
    days = pd.date_range("2026-05-01", periods=MIN_PAIRED_DAYS - 1, freq="D")
    master = pd.DataFrame({"date": days, "apple_shazams": range(len(days)),
                           "streams": range(len(days))})
    assert shazam_stream_lag(master) is None
