"""Record every query a view sends, so a test can assert what it read — not what it said.

Written 2026-08-22 for R25. The first version of `test_stray_session_reads_nothing`
asserted that a view printed "Session invalide", and that was the wrong question:
`upload_csv` refuses a tenant-less session correctly, with its own clearer message,
and failed. Meanwhile a view could print the right words and still have queried three
tables on the way there.

The property is about the DATABASE, so this measures the database.

Patching happens on `PostgresHandler` itself rather than on `get_db_connection`.
Views bind `get_db_connection` at import time (`from ... import get_db_connection`),
so patching the factory only works if you win a race with the first import. Method
lookup on the returned object goes through the class every call, and cannot be missed.
"""
from __future__ import annotations

import re

RECORDED: list[tuple[str, object]] = []

# Tables holding one tenant's rows. A query touching one of these without a tenant
# filter reads every tenant.
_TENANT_TABLES = (
    "s4a_song_timeline", "s4a_song_algo_outcomes", "youtube_videos",
    "youtube_channels", "youtube_video_stats", "soundcloud_tracks",
    "instagram_media", "instagram_insights", "apple_music_songs",
    "meta_ads_insights", "meta_campaigns", "artist_credentials",
    "artist_subscriptions", "ml_song_predictions", "imusician_revenues",
    "distrokid_revenues", "sacem_revenues", "track_platform_link",
    "referral_events", "usage_events",
)

# What counts as scoping a read: a tenant column compared to something. The value is
# checked separately — `artist_id = %s` with a None parameter filters nothing.
_SCOPED = re.compile(r"\b(artist_id|saas_artist_id)\s*(=|IN)\b", re.I)


def install(monkeypatch=None) -> list:
    """Start recording. Returns the list that will hold (query, params) pairs."""
    from src.database.postgres_handler import PostgresHandler

    RECORDED.clear()
    for name in ("fetch_df", "fetch_query", "execute_query"):
        original = getattr(PostgresHandler, name)
        # install() is called once per AppTest script, in the same process. Without
        # this, run N wraps run N-1's wrapper and each query is recorded N times —
        # harmless for the assertion, quadratic for the suite.
        if getattr(original, "_is_query_spy", False):
            continue

        def _wrapped(self, query, params=None, __orig=original, **kwargs):
            RECORDED.append((str(query), params))
            return __orig(self, query, params, **kwargs)

        _wrapped._is_query_spy = True
        if monkeypatch is not None:
            monkeypatch.setattr(PostgresHandler, name, _wrapped)
        else:
            setattr(PostgresHandler, name, _wrapped)
    return RECORDED


def unscoped_tenant_reads() -> list[str]:
    """Queries that touched a tenant table with no usable tenant filter."""
    offenders = []
    for query, params in RECORDED:
        low = query.lower()
        if not any(t in low for t in _TENANT_TABLES):
            continue
        if not _SCOPED.search(query):
            offenders.append(query)
            continue
        # `artist_id = %s` bound to None is not a filter — it is `= NULL`, which
        # matches nothing, but it also means the caller believed it had a tenant.
        values = params if isinstance(params, (tuple, list)) else (params,)
        if params is not None and all(v is None for v in values):
            offenders.append(query)
    return offenders
