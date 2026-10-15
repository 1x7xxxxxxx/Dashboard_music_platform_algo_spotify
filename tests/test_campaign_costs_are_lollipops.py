"""R576 — CPM, CPC and CPR each get their own panel and scale, cheapest CPR on top.

Type: Guard
Uses: src/dashboard/views/meta_ads_overview.py (_perf_costs)
Depends on: nothing (pure figure)
Persists in: nothing

Owner, 2026-10-15: « présenter CPC/CPR/CPM plus joliment ». Grouped bars on one €-axis
crushed the CPC under the CPM; three lollipop panels give each cost its own scale.
"""
from __future__ import annotations

import pandas as pd

from src.dashboard.views.meta_ads_overview import _perf_costs

_D = pd.DataFrame({"campaign_name": ["A", "B", "C"], "spend": [100.0, 50.0, 10.0],
                   "impressions": [20_000, 5_000, 1_000], "link_clicks": [400, 50, 20],
                   "custom_conversions": [100, 5, 0]})


def test_each_cost_has_its_own_panel_and_scale() -> None:
    fig = _perf_costs(_D, ["A", "B", "C"])
    assert {tr.xaxis for tr in fig.data} == {"x", "x2", "x3"}
    assert fig.layout.xaxis.range[1] != fig.layout.xaxis2.range[1], "one scale per cost"


def test_the_cheapest_cpr_is_on_top_and_an_undefined_one_is_not_drawn() -> None:
    fig = _perf_costs(_D, ["A", "B", "C"])
    order = list(fig.layout.yaxis.categoryarray)
    assert order[-1] == "A", "Plotly stacks from the bottom: the cheapest CPR goes last"
    cpr_dots = [tr for tr in fig.data if tr.xaxis == "x3" and tr.type == "scatter"][0]
    assert "C" not in list(cpr_dots.y), "C has no result: no CPR dot at 0"


def test_each_panel_is_framed_and_its_best_cost_marked() -> None:
    """R593 — a dotted box per panel, a dotted vertical at the lowest cost of each."""
    fig = _perf_costs(_D, ["A", "B", "C"])
    rects = [s for s in fig.layout.shapes if s.type == "rect"]
    assert len(rects) == 3 and all(s.line.dash == "dot" for s in rects)
    lines = {s.xref: s.x0 for s in fig.layout.shapes if s.type == "line"}
    assert all(s.line.dash == "dot" for s in fig.layout.shapes if s.type == "line")
    for ax in ("x", "x2", "x3"):
        dots = [tr for tr in fig.data if tr.xaxis == ax and tr.type == "scatter"][0]
        assert lines[ax] == min(dots.x), f"{ax}: the vertical sits on the best cost"
