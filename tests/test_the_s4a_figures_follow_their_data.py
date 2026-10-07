"""Spotify + S4A figures follow their data (R382, V28/V31-V33, owner 2026-10-05).

Type: Guard
Uses: src/dashboard/views/spotify_s4a_combined.py (meta_spend_traces,
      popularity_axis_max, moving_songs)
Depends on: pandas, plotly — no database
Persists in: nothing

* the Meta area draws spend PER DAY (R459, reversing R382's cumulation), and the
  dotted style has its own legend entry;
* the popularity axis top is the observed max rounded up to ten, not a fixed 100;
* the title selector keeps only the titles at >= 1 stream/day over the recent window.
"""
from __future__ import annotations

import pandas as pd

from src.dashboard.views import spotify_s4a_combined as page


def test_the_meta_trace_is_per_day_not_cumulative() -> None:
    """R459 (owner, 2026-10-07): « Meta Euro par jour uniquement ». Mutated red: cumsum back."""
    meta = pd.DataFrame({"title": ["a", "a", "a", "b"], "day_index": [0, 1, 3, 2],
                         "spend": [4.0, 2.0, 6.0, 5.0]})
    traces = {tr.name: list(tr.y) for tr in page.meta_spend_traces(meta, {})}
    assert traces["a"] == [4.0, 2.0, 0.0, 6.0]
    assert traces["b"] == [5.0]


def test_the_dotted_lines_are_named_in_the_legend() -> None:
    """R459: « la légende fait référence qu'au trait plein ». Mutated red: showlegend off."""
    import ast
    import inspect

    entry = page.meta_legend_trace()
    assert entry.showlegend and entry.line.dash == "dot"
    tree = ast.parse(inspect.getsource(page))
    dotted_named = [kw for n in ast.walk(tree) if isinstance(n, ast.Call)
                    and getattr(n.func, "attr", "") == "Scatter"
                    for kw in n.keywords if kw.arg == "showlegend"
                    and getattr(kw.value, "value", None) is True]
    # the Meta legend entry and the popularity series
    assert len(dotted_named) >= 2


def test_the_popularity_axis_follows_the_observed_max() -> None:
    assert page.popularity_axis_max(pd.Series([3, 12, 9])) == 20
    assert page.popularity_axis_max(pd.Series([41, 55])) == 60
    assert page.popularity_axis_max(pd.Series([2])) == 10
    assert page.popularity_axis_max(pd.Series([97])) == 100
    assert page.popularity_axis_max(pd.Series([], dtype=float)) == 100


def test_the_title_picker_keeps_the_titles_that_move() -> None:
    spans = pd.DataFrame({"song": ["old", "new", "quiet"]})
    recent = pd.DataFrame({"song": ["new", "quiet"], "recent": [120, 27]})
    assert page.moving_songs(spans, recent)["song"].tolist() == ["new"]
    nobody = pd.DataFrame({"song": ["quiet"], "recent": [27]})
    assert page.moving_songs(spans, nobody)["song"].tolist() == ["old", "new", "quiet"]
