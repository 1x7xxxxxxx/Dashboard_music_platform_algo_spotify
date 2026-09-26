"""A gold view shows a tenant the same rows whether or not ANOTHER tenant has data.

Type: Sub
Uses: the live `spotify_etl` schema (gold views of Apple Music, Instagram, Spotify S4A,
      YouTube), saas_artists
Depends on: tests/db_gate.py (skips without a live Postgres)
Persists in: nothing — both synthetic tenants and their rows are deleted on exit

R180 (2026-09-26). The `plateforme × famille` matrix of `.claude/dev-docs/gold-coverage.md`
had four empty `le-locataire` cells: no guard read a gold view of these four platforms with
two tenants in the base. A per-tenant `WHERE artist_id = %s` in the CALLER proves nothing
about a join INSIDE the view that forgot the tenant key — tenant B's rows then leak into
tenant A's aggregates, under A's `artist_id`, and every caller-side guard stays green.

The property, measured directly: seed tenant A, read each view for A; seed tenant B on the
SAME keys (song names, dates, ids) with numbers 1000x larger; read again. The two reads
must be identical. « B's rows do not appear under A » alone would miss the leak that
matters — a join that ADDS B's streams to A's row.

Class: `a-late-platform-has-no-tenant-guard` (family `le-locataire`).
"""
from __future__ import annotations

import datetime as dt
import uuid

import pytest

from tests.db_gate import requires_live_db

pytestmark = [pytest.mark.xdist_group("gold-two-tenants"), requires_live_db()]

# Raw tables seeded, per platform. Their columns are filled generically from the schema.
_SEEDED = ("apple_songs_performance", "apple_songs_history", "instagram_daily_stats",
           "instagram_media", "s4a_song_timeline", "s4a_audience", "s4a_songs_global",
           "youtube_video_stats", "youtube_channel_history")

# One literal read per view, so the coverage matrix sees WHICH views are guarded.
_VIEWS = {
    "v_apple_song_cumulative": "SELECT * FROM v_apple_song_cumulative WHERE artist_id = %s",
    "v_apple_song_daily": "SELECT * FROM v_apple_song_daily WHERE artist_id = %s",
    "v_instagram_followers_daily":
        "SELECT * FROM v_instagram_followers_daily WHERE artist_id = %s",
    "v_instagram_media_monthly": "SELECT * FROM v_instagram_media_monthly WHERE artist_id = %s",
    "v_s4a_song_daily": "SELECT * FROM v_s4a_song_daily WHERE artist_id = %s",
    "v_s4a_song_measured_span": "SELECT * FROM v_s4a_song_measured_span WHERE artist_id = %s",
    "v_s4a_audience_daily": "SELECT * FROM v_s4a_audience_daily WHERE artist_id = %s",
    "v_s4a_audience_monthly": "SELECT * FROM v_s4a_audience_monthly WHERE artist_id = %s",
    "v_s4a_release_cohort": "SELECT * FROM v_s4a_release_cohort WHERE artist_id = %s",
    "v_s4a_release_reach": "SELECT * FROM v_s4a_release_reach WHERE artist_id = %s",
    "v_spotify_followers_daily": "SELECT * FROM v_spotify_followers_daily WHERE artist_id = %s",
    "v_platform_levels": "SELECT * FROM v_platform_levels WHERE artist_id = %s",
    "v_platform_totals": "SELECT * FROM v_platform_totals WHERE artist_id = %s",
}

_DAYS = 3


def leaked_views(read, views, seed_other) -> list[str]:
    """Views whose rows for tenant A change once tenant B is seeded. Pure: `read(sql)` returns
    A's rows, `seed_other()` seeds B."""
    before = {name: sorted(map(repr, read(sql))) for name, sql in views.items()}
    seed_other()
    return sorted(name for name, sql in views.items()
                  if sorted(map(repr, read(sql))) != before[name])


def _value(data_type: str, day: int, scale: int, col: str, tenant: int):
    if data_type == "date":
        return dt.date.today() - dt.timedelta(days=day + 1)
    if data_type.startswith("timestamp"):
        return dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=day + 1)
    if data_type in ("integer", "bigint", "smallint", "numeric", "double precision", "real"):
        return (day + 1) * scale
    if data_type == "boolean":
        return False
    if data_type in ("json", "jsonb"):
        return "{}"
    # Shared keys across tenants: the leak that matters joins on them.
    return f"gold-2t-{col}-{day}"


def _seed(db, tenant: int, scale: int) -> None:
    for table in _SEEDED:
        cols = db.fetch_query(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s AND is_identity = 'NO' "
            "AND is_generated = 'NEVER' AND coalesce(column_default, '') NOT LIKE 'nextval%%' "
            "AND column_name NOT IN ('created_at', 'updated_at', 'imported_at') "
            "ORDER BY ordinal_position", (table,))
        for day in range(_DAYS):
            names, values = [], []
            for col, data_type in cols:
                names.append(col)
                values.append(tenant if col == "artist_id"
                              else _value(data_type, day, scale, col, tenant))
            db.execute_query(
                f"INSERT INTO {table} ({', '.join(names)}) "  # names from information_schema
                f"VALUES ({', '.join(['%s'] * len(values))}) ON CONFLICT DO NOTHING",
                tuple(values))
    # The release views join a CONFIRMED s4a link and a release date (migration 049): one
    # per seeded song, released before the first seeded day.
    for day in range(_DAYS):
        song, key = f"gold-2t-song-{day}", f"gold-2t-key-{day}"
        db.execute_query(
            "INSERT INTO track_release_reference (artist_id, match_key, title, release_date) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (tenant, key, song, dt.date.today() - dt.timedelta(days=_DAYS + 5)))
        db.execute_query(
            "INSERT INTO track_platform_link (artist_id, match_key, platform, platform_title, "
            "status) VALUES (%s, %s, 's4a', %s, 'confirmed') ON CONFLICT DO NOTHING",
            (tenant, key, song))


@pytest.fixture
def db():
    from src.dashboard.utils import get_db_connection
    conn = get_db_connection()
    yield conn
    conn.close()


@pytest.fixture
def two_tenants(db):
    ids = []
    for _ in range(2):
        slug = f"gold2t-{uuid.uuid4().hex[:10]}"
        ids.append(db.fetch_query(
            "INSERT INTO saas_artists (name, slug, tier, active) VALUES (%s, %s, 'free', FALSE) "
            "RETURNING id", (slug, slug))[0][0])
    yield ids
    for table in _SEEDED + ("track_platform_link", "track_release_reference"):
        db.execute_query(f"DELETE FROM {table} WHERE artist_id = ANY(%s)", (ids,))
    db.execute_query("DELETE FROM saas_artists WHERE id = ANY(%s)", (ids,))


def test_a_gold_view_is_blind_to_another_tenants_rows(db, two_tenants) -> None:
    a, b = two_tenants
    _seed(db, a, scale=1)
    empty = [n for n, sql in _VIEWS.items() if not db.fetch_query(sql, (a,))]
    assert not empty, (f"{empty} render nothing for a seeded tenant — the comparison below "
                       "would be vacuous for them; seed what these views need.")
    leaked = leaked_views(lambda sql: db.fetch_query(sql, (a,)), _VIEWS,
                          lambda: _seed(db, b, scale=1000))
    assert not leaked, (f"{leaked} : tenant {a}'s rows changed when tenant {b} got data on the "
                        "same keys — a join inside the view does not carry `artist_id`.")


def test_the_detector_sees_the_defect_it_is_written_for(db, two_tenants) -> None:
    """Non-vacuity: a view that sums s4a_song_timeline by song and date WITHOUT the tenant key
    is caught; the same view keyed by artist_id is not."""
    a, b = two_tenants
    tag = uuid.uuid4().hex[:8]
    leaky, sound = f"tmp_leaky_{tag}", f"tmp_sound_{tag}"
    db.execute_query(
        f"CREATE TEMP VIEW {leaky} AS SELECT t.artist_id, t.song, t.date, "
        "(SELECT SUM(x.streams) FROM s4a_song_timeline x WHERE x.song = t.song "
        "AND x.date = t.date) AS streams FROM s4a_song_timeline t")
    db.execute_query(
        f"CREATE TEMP VIEW {sound} AS SELECT t.artist_id, t.song, t.date, "
        "(SELECT SUM(x.streams) FROM s4a_song_timeline x WHERE x.song = t.song "
        "AND x.date = t.date AND x.artist_id = t.artist_id) AS streams FROM s4a_song_timeline t")
    views = {leaky: f"SELECT * FROM {leaky} WHERE artist_id = %s",
             sound: f"SELECT * FROM {sound} WHERE artist_id = %s"}
    _seed(db, a, scale=1)
    assert all(db.fetch_query(sql, (a,)) for sql in views.values()), "the probe reads nothing"
    assert leaked_views(lambda sql: db.fetch_query(sql, (a,)), views,
                        lambda: _seed(db, b, scale=1000)) == [leaky]
