"""Apple Music: the Shazams are a chart beside the top 10, not a folded table (R383).

Type: Guard
Uses: src.dashboard.views.apple_music (_shazam_bar), tests/render_harness.py (TENANT_SCRIPT)
Depends on: live Postgres with artist 1's Apple readings for the render (skipped without)
Persists in: nothing

V37 (owner's screen review, 2026-10-05): « Shazams par chanson » was an expander under the
top-10 chart. It becomes a chart on the same row, to the right, in the same title order —
one title reads across both frames.
"""
from __future__ import annotations

import os

import pandas as pd
import pytest

from tests.db_gate import db_ready
from tests.render_harness import TENANT_SCRIPT


def test_the_shazam_chart_keeps_the_streams_order() -> None:
    from src.dashboard.views.apple_music import _shazam_bar

    df = pd.DataFrame({"song_name": ["a", "b", "c"], "plays": [30, 10, 20],
                       "shazam_count": [1, 9, 5]})
    fig = _shazam_bar(df)
    assert list(fig.layout.yaxis.categoryarray) == ["b", "c", "a"], (
        "the Shazam bars are not in the streams order of the chart beside them")


def _has_apple() -> bool:
    from src.dashboard.utils import get_db_connection

    db = get_db_connection()
    try:
        return bool(db.fetch_query(
            "SELECT 1 FROM v_apple_song_cumulative WHERE artist_id = 1 LIMIT 1"))
    finally:
        db.close()


@pytest.mark.skipif(not db_ready(), reason="renders the Apple Music page against the live DB")
def test_the_top10_row_holds_two_charts_and_no_shazam_expander() -> None:
    if not _has_apple():
        pytest.skip("artist 1 has no Apple reading — the page renders its empty state")
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(TENANT_SCRIPT.format(root=os.getcwd(), view="apple_music",
                                                  artist_id=1))
    at.run(timeout=120)
    assert not at.exception, at.exception
    assert not [e.label for e in at.expander if "Shazams par chanson" in e.label], (
        "the Shazams are folded in an expander again")
    assert any(_both_columns_chart(b) for b in _blocks(at._tree)), (
        "no st.columns(2) row carries the top 10 and the Shazams side by side")


def _blocks(node):
    for child in getattr(node, "children", {}).values():
        yield child
        yield from _blocks(child)


def _both_columns_chart(block) -> bool:
    """A horizontal row of exactly two columns, each drawing a Plotly chart."""
    cols = [c for c in getattr(block, "children", {}).values() if c.type == "column"]
    return (len(cols) == 2 == len(block.children)
            and all(c.get("plotly_chart") for c in cols))
