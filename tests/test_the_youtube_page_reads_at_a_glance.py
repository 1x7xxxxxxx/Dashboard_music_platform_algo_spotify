"""YouTube: the top read at a glance, views gained as a difference, no explanatory text (R384, R485).

Type: Guard
Uses: src/dashboard/views/youtube.py (top_figure, pareto_share, pace, channel_figure,
      views_gained, show),
      tests/render_harness.py (TENANT_SCRIPT)
Depends on: pandas; live Postgres with artist 1's YouTube readings for the render
Persists in: nothing

V38-V41 (owner's screen review, 2026-10-05): « Évolution de la chaîne » stays, the
explanatory captions go; the views × likes cloud becomes a ranking by like/view ratio;
more figures on data already collected. Subscribers gained PER VIDEO are not collected
(Data API v3 only — R394).

R485 (W8, 2026-10-09) : the ratio ranking, the content-type selector and the age × views
cloud are gone — top 10 as views + likes side by side, two Pareto (videos, shorts), and
the recent pace of each video.
"""
from __future__ import annotations

import os

import pandas as pd
import pytest

from src.dashboard.views import youtube as page
from tests.db_gate import db_ready
from tests.render_harness import TENANT_SCRIPT


def _videos() -> pd.DataFrame:
    return pd.DataFrame({"video_id": ["a", "b", "c"], "title": ["small", "big", "mid"],
                         "view_count": [100, 1_000, 400], "like_count": [5, 10, 40],
                         "published_at": ["2026-01-01T00:00:00Z"] * 3})


def test_the_top_chart_puts_the_most_viewed_video_on_top() -> None:
    """R485 (W8) : « on ne voit pas d'un coup d'œil quelle vidéo marche ». Horizontal bars
    draw bottom-up, so the most viewed is the LAST point of each panel."""
    fig = page.top_figure(_videos())
    views, likes = fig.data
    assert list(views.x) == [100, 400, 1_000]
    assert views.y[-1].endswith("big") and likes.y[-1].endswith("big")
    assert list(likes.x) == [5, 40, 10], "likes must ride on the same rows as views"


def test_the_pareto_share_is_cumulative_biggest_first() -> None:
    assert page.pareto_share(pd.Series([100, 1_000, 400])) == pytest.approx(
        [1000 / 15, 1400 / 15, 100.0])
    assert page.pareto_share(pd.Series([0, 0])) == [0.0, 0.0]


def test_the_recent_pace_reads_the_last_window_before_the_last_reading() -> None:
    """A collection that stopped weeks ago still answers : the window ends at the last
    reading, not today. A reading older than the window does not count."""
    last = pd.Timestamp("2026-06-30", tz="UTC")
    readings = pd.DataFrame({
        "video_id": ["a", "a", "a", "b", "b", "c"],
        "collected_at": [last - pd.Timedelta(days=90), last - pd.Timedelta(days=10), last,
                         last - pd.Timedelta(days=20), last, last],
        "view_count": [0, 90, 100, 1_000, 1_100, 400]})
    paced = page.pace(_videos(), readings)
    assert paced["title"].tolist() == ["big", "small"], "c has one reading : no pace"
    assert paced["recent"].tolist() == pytest.approx([5.0, 1.0])


def test_the_channel_chart_stacks_subscribers_and_views() -> None:
    hist = pd.DataFrame({"date": pd.to_datetime(["2026-01-01", "2026-02-01"]),
                         "subs": [10, 12]})
    fig = page.channel_figure(hist, [(pd.Timestamp("2026-01-01"), 100),
                                     (pd.Timestamp("2026-02-01"), 150)])
    subs, views = fig.data
    assert views.yaxis == "y2" and not fig.layout.yaxis2.overlaying, "two panels, not a twin axis"
    assert views.xaxis == "x2" and fig.layout.xaxis.matches == "x2", "one shared time axis"
    assert subs.line.color != views.line.color, "W8 : « tout rouge = moche »"


def test_views_gained_is_a_difference_of_counters_not_a_sum() -> None:
    day = pd.Timestamp("2026-09-01")
    readings = pd.DataFrame({
        "video_id": ["a", "a", "a", "b", "b", "c"],
        "title": ["A", "A", "A", "B", "B", "C"],
        "collected_at": [day, day + pd.Timedelta(days=1), day + pd.Timedelta(days=2),
                         day, day + pd.Timedelta(days=2), day],
        "view_count": [1_000, 1_010, 1_050, 300, 300, 9_999]})
    gained = page.views_gained(readings)
    assert gained.to_dict("records") == [{"title": "A", "gained": 50}]


@pytest.mark.skipif(not db_ready(), reason="renders the YouTube page against the live DB")
def test_the_page_has_no_explanatory_caption() -> None:
    from streamlit.testing.v1 import AppTest

    from src.dashboard.utils import get_db_connection

    db = get_db_connection()
    try:
        if not db.fetch_query("SELECT 1 FROM v_youtube_video_latest WHERE artist_id = 1 LIMIT 1"):
            pytest.skip("artist 1 has no YouTube video — the page renders its empty state")
    finally:
        db.close()
    at = AppTest.from_string(TENANT_SCRIPT.format(root=os.getcwd(), view="youtube",
                                                  artist_id=1))
    at.run(timeout=120)
    assert not at.exception, at.exception
    heads = [h.value for h in at.subheader]
    assert any("Top Contenus" in h for h in heads), f"the videos section did not render: {heads}"
    assert not at.error, [e.value for e in at.error]
    long_texts = [c.value for c in at.caption if len(c.value) > 120]
    assert not long_texts, f"an explanatory caption is back: {long_texts}"


def test_a_series_that_differs_only_at_its_end_keeps_readable_distinct_labels() -> None:
    """Ten « DJ Set … Detroit N » cut at 40 characters drew ten identical prefixes: the
    rank told them apart, the reader could not. The tail must survive the cut."""
    from src.dashboard.views.youtube import _labels

    titles = [f"DJ Set multicamera Hardtechno Rave Schranz de Detroit {n}" for n in (17, 16)]
    labels = _labels(titles)
    assert labels[0].startswith("1. ") and labels[1].startswith("2. ")
    assert labels[0].endswith("Detroit 17") and labels[1].endswith("Detroit 16"), labels
