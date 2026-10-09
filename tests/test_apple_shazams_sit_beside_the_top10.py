"""Apple Music: the Shazams are a chart beside the top 10, not a folded table (R383).

Type: Guard
Uses: src.dashboard.views.apple_music (_top10_figure), tests/render_harness.py (TENANT_SCRIPT)
Depends on: live Postgres with artist 1's Apple readings for the render (skipped without)
Persists in: nothing

V37 (owner's screen review, 2026-10-05): « Shazams par chanson » was an expander under the
top-10 chart. It becomes a chart on the same row, to the right, in the same title order —
one title reads across both frames. R484 (W7 II) makes them the right PANEL of the same
figure, sharing the y axis: on two half-page charts the names were written twice.
"""
from __future__ import annotations

import os

import pandas as pd
import pytest

from tests.db_gate import db_ready
from tests.render_harness import TENANT_SCRIPT


def test_the_shazams_share_the_rows_of_the_streams() -> None:
    from src.dashboard.views.apple_music import _top10_figure

    df = pd.DataFrame({"song_name": ["a", "b", "c"], "plays": [30, 10, 20],
                       "shazam_count": [1, 9, 5]})
    fig = _top10_figure(df, "60", "15")
    streams, shazams = fig.data
    assert list(streams.y) == list(shazams.y) == ["b", "c", "a"], (
        "the Shazam bars are not on the rows of the streams beside them")
    assert fig.layout.yaxis2.matches == "y", "the two panels do not share the titles"
    titles = [a.text for a in fig.layout.annotations]
    assert any("60" in x for x in titles) and any("15" in x for x in titles), (
        f"the totals are not in the panel titles : {titles}")


def _has_apple() -> bool:
    from src.dashboard.utils import get_db_connection

    db = get_db_connection()
    try:
        return bool(db.fetch_query(
            "SELECT 1 FROM v_apple_song_cumulative WHERE artist_id = 1 LIMIT 1"))
    finally:
        db.close()


@pytest.mark.skipif(not db_ready(), reason="renders the Apple Music page against the live DB")
def test_the_page_draws_the_top10_with_its_shazams_and_no_expander() -> None:
    if not _has_apple():
        pytest.skip("artist 1 has no Apple reading — the page renders its empty state")
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(TENANT_SCRIPT.format(root=os.getcwd(), view="apple_music",
                                                  artist_id=1))
    at.run(timeout=120)
    assert not at.exception, at.exception
    assert not [e.label for e in at.expander if "Shazams par chanson" in e.label], (
        "the Shazams are folded in an expander again")
    assert len(at.get("plotly_chart")) == 2, "top 10 + Shazams, then the pace of one title"
