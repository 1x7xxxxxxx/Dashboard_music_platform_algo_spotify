"""R273 — Instagram media insights ask for metrics Meta still serves, and a request that
every media refuses fails the run instead of saving nothing.

Type: Test
Uses: src/collectors/instagram_api_collector.py (INSIGHT_METRICS, fetch_media_insights)

Measured 2026-09-27, local AND production: 51 media, 0 insight rows, every media skipped
with code 100. Meta removed `impressions` on 2025-04-21 for every API version (folded into
`views`), `engagement` became `total_interactions`, and one removed metric fails the whole
request. The skip was « per media, legitimate » — 51 times out of 51.

Mutation record (2026-09-27) : `impressions` put back in INSIGHT_METRICS → red ; the
all-refused raise removed → red ; `views` no longer mapped → red.
"""
from unittest.mock import MagicMock

import pytest

from src.collectors import instagram_api_collector as ig

_REMOVED = {"impressions", "engagement", "plays", "video_views", "clips_replays_count",
            "ig_reels_aggregated_all_plays_count"}


def _collector(responses):
    c = ig.InstagramCollector.__new__(ig.InstagramCollector)
    c.artist_id, c.access_token, c.base_url = 7, "tok", "https://graph.example/v22.0"
    c.session = MagicMock()
    c.session.get.side_effect = responses
    return c


def _resp(status, body):
    r = MagicMock(status_code=status, content=b"x")
    r.json.return_value = body
    return r


def test_no_removed_metric_is_requested():
    asked = set(ig.INSIGHT_METRICS.split(","))
    assert not asked & _REMOVED, f"métriques retirées par Meta : {asked & _REMOVED}"
    assert {"views", "total_interactions"} <= asked


def test_every_media_refused_fails_the_run():
    refused = _resp(400, {"error": {"code": 100, "message": "(#100) Incompatible metric"}})
    c = _collector([refused, refused])
    with pytest.raises(ValueError, match="refusées"):
        ig.InstagramCollector.fetch_media_insights.__wrapped__(c, ["a", "b"]) \
            if hasattr(ig.InstagramCollector.fetch_media_insights, "__wrapped__") \
            else c.fetch_media_insights(["a", "b"])


def test_one_refused_media_among_served_ones_is_skipped_and_views_land_in_the_row():
    ok = _resp(200, {"data": [{"name": "views", "values": [{"value": 120}]},
                              {"name": "total_interactions", "values": [{"value": 9}]}]})
    refused = _resp(400, {"error": {"code": 100, "message": "album child"}})
    c = _collector([ok, refused])
    fn = getattr(ig.InstagramCollector.fetch_media_insights, "__wrapped__", None)
    rows = fn(c, ["a", "b"]) if fn else c.fetch_media_insights(["a", "b"])
    assert len(rows) == 1 and rows[0]["impressions"] == 120 and rows[0]["engagement"] == 9
