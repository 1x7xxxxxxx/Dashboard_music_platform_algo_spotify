"""YouTube: ranked by likes per view, views gained as a difference, no explanatory text (R384).

Type: Guard
Uses: src/dashboard/views/youtube.py (like_ratio_ranking, views_gained, show),
      tests/render_harness.py (TENANT_SCRIPT)
Depends on: pandas; live Postgres with artist 1's YouTube readings for the render
Persists in: nothing

V38-V41 (owner's screen review, 2026-10-05): « Évolution de la chaîne » stays, the
explanatory captions go; the views × likes cloud becomes a ranking by like/view ratio;
more figures on data already collected. Subscribers gained PER VIDEO are not collected
(Data API v3 only — R394).
"""
from __future__ import annotations

import os

import pandas as pd
import pytest

from src.dashboard.views import youtube as page
from tests.db_gate import db_ready
from tests.render_harness import TENANT_SCRIPT


def test_the_best_ratio_comes_first() -> None:
    videos = pd.DataFrame({"title": ["big", "loved", "unseen", "meh"],
                           "view_count": [10_000, 200, 0, 1_000],
                           "like_count": [100, 20, 0, 5],
                           "comment_count": [10, 0, 0, 1]})
    ranked = page.like_ratio_ranking(videos)
    assert ranked["title"].tolist() == ["loved", "big", "meh"]
    assert ranked["label"].tolist()[0] == "1. loved"
    assert ranked["comments_per_k"].tolist() == [0.0, 1.0, 1.0]


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
def test_the_page_has_no_explanatory_caption_and_ranks_by_ratio() -> None:
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
