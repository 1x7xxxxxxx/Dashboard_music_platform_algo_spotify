"""R530 — the YouTube Analytics figures, held to what the real data of artist 1 showed.

Type: Test
Uses: src.dashboard.views.youtube (figure builders)
Depends on: src/dashboard/utils/platform_colors.py (DISTINCT: five colours)
Persists in: nothing

1. a day the API did not deliver stays a gap — no bar; the 7-day mean (R535) is continuous;
2. a channel under 2 h a day is drawn in minutes, a bigger one in hours;
3. the traffic chart never has more traces than the colorway has colours;
4. R547 (owner, 2026-10-12): watch time and traffic per day close the channel tab, and
   the Analytics tab label no longer says « données exactes ».

Mutation record — 2026-10-12: `_daily_section(...)` moved above `_videos_section(...)`
→ test 4 red; « — données exactes » put back in the label → test 4 red.
"""
from __future__ import annotations

import ast
import inspect
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
    assert math.isnan(tr.y[2]) and math.isnan(tr.y[3]), "an absent day was drawn as a bar"


def test_watch_time_is_daily_bars_under_a_continuous_7_day_mean():
    """R535 — the bars carry the day, the mean carries the trend across a gap."""
    fig = youtube.watch_time_figure(_daily(["2026-09-12", "2026-09-13", "2026-09-16"],
                                           [3, 6, 2]))
    bars, mean = fig.data
    assert bars.type == "bar" and mean.type == "scatter"
    assert not any(math.isnan(v) for v in mean.y), "the 7-day mean broke on a missing day"
    assert list(mean.y)[-1] == (3 + 6 + 2) / 3, "the mean averaged invented zeros"


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


def test_the_daily_series_close_the_channel_tab_and_the_label_claims_nothing():
    tree = ast.parse(inspect.getsource(youtube.show))
    channel = next(w for w in ast.walk(tree) if isinstance(w, ast.With)
                   and ast.unparse(w.items[0].context_expr) == "tab_channel")
    calls = [ast.unparse(n.value.func) for n in channel.body
             if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)]
    assert calls[-1] == "_daily_section", (
        f"R547: watch time and traffic per day must END the channel tab, got {calls}")
    def _called(fn) -> set[str]:
        return {ast.unparse(n.func) for n in ast.walk(ast.parse(inspect.getsource(fn)))
                if isinstance(n, ast.Call)}

    assert {"watch_time_figure", "traffic_figure"} <= _called(youtube._daily_section)
    assert "watch_time_figure" not in _called(youtube._analytics_section)
    tabs = next(n for n in ast.walk(tree) if isinstance(n, ast.Call)
                and ast.unparse(n.func) == "st.tabs")
    labels = [c.value for c in ast.walk(tabs.args[0])
              if isinstance(c, ast.Constant) and isinstance(c.value, str)]
    assert labels and not any("exactes" in lab for lab in labels), (
        f"R547: « données exactes » implied the channel tab is not exact: {labels}")
