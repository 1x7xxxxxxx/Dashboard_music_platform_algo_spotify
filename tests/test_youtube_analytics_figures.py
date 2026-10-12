"""R530 — the YouTube Analytics figures, held to what the real data of artist 1 showed.

Type: Test
Uses: src.dashboard.views.youtube (figure builders)
Depends on: src/dashboard/utils/platform_colors.py (DISTINCT: five colours)
Persists in: nothing

1. a day the API did not deliver stays a gap — no segment drawn across it;
2. a channel under 2 h a day is drawn in minutes, a bigger one in hours;
3. the traffic chart never has more traces than the colorway has colours.
"""
from __future__ import annotations

import math

import pandas as pd

from src.dashboard.utils.platform_colors import DISTINCT
from src.dashboard.views import youtube


def _daily(days, minutes):
    return pd.DataFrame({"day": pd.to_datetime(days), "minutes_watched": minutes})


def test_a_missing_day_stays_a_gap():
    fig = youtube.watch_time_figure(_daily(["2026-09-12", "2026-09-13", "2026-09-16"],
                                           [3, 6, 2]))
    tr = fig.data[0]
    assert len(tr.x) == 5, "the absent days were not put back on the axis"
    assert math.isnan(tr.y[2]) and math.isnan(tr.y[3])
    assert tr.connectgaps is False


def test_a_small_channel_reads_in_minutes_a_big_one_in_hours():
    small = youtube.watch_time_figure(_daily(["2026-09-12", "2026-09-13"], [3, 6]))
    assert list(small.data[0].y) == [3, 6]
    big = youtube.watch_time_figure(_daily(["2026-09-12", "2026-09-13"], [120, 600]))
    assert list(big.data[0].y) == [2, 10]
    assert small.layout.yaxis.title.text != big.layout.yaxis.title.text


def _traffic(n_sources):
    return pd.DataFrame([{"day": "2026-09-12", "source_type": f"S{i}", "views": 10 + i}
                         for i in range(n_sources)])


def test_traffic_never_outruns_the_colorway():
    fig = youtube.traffic_figure(_traffic(7))
    assert len(fig.data) == len(DISTINCT) == 5
    assert sum(sum(t.y) for t in fig.data) == sum(10 + i for i in range(7)), "views lost"
    assert len(youtube.traffic_figure(_traffic(5)).data) == 5, "five sources were folded"
