"""Tests for the pure per-artist readiness logic (src/utils/artist_readiness.py).

Guards the closed-loop that makes a connected-but-0-rows tenant (the Benken silent gap)
a visible RED status + an exact next action, per artist × platform.
"""
from datetime import datetime

from src.utils import artist_readiness as ar


def test_no_identity_is_todo():
    assert ar.platform_status(False, None, True) == ar.TODO
    assert ar.platform_status(False, datetime(2026, 6, 1), False) == ar.TODO  # identity gates first


def test_identity_but_no_data_is_red():
    assert ar.platform_status(True, None, True) == ar.NO_DATA


def test_identity_and_stale_data_is_amber():
    assert ar.platform_status(True, datetime(2026, 6, 1), True) == ar.STALE


def test_identity_and_fresh_data_is_green():
    assert ar.platform_status(True, datetime(2026, 6, 20), False) == ar.OK


def test_next_action_is_actionable_per_status():
    meta = next(p for p in ar._PLATFORMS if p["key"] == "meta")
    assert ar.next_action(meta, ar.OK) == ""
    assert "Renseigne" in ar.next_action(meta, ar.TODO)
    # the headline guidance: connected-but-no-data Meta → asset-sharing
    assert "asset sharing" in ar.next_action(meta, ar.NO_DATA)
    assert "DAG meta" in ar.next_action(meta, ar.STALE)


def test_youtube_no_data_hint_mentions_topic_channel():
    yt = next(p for p in ar._PLATFORMS if p["key"] == "youtube")
    assert "Topic" in ar.next_action(yt, ar.NO_DATA)


def test_every_platform_has_an_icon_and_hints():
    for p in ar._PLATFORMS:
        assert p["id_hint"] and p["nodata_hint"]
        for s in (ar.TODO, ar.NO_DATA, ar.STALE, ar.OK):
            assert s in ar._ICON and s in ar._LABEL
