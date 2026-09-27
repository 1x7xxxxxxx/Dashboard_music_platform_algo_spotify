"""A one-day Apple export gives that day's Shazams; cumulative exports never cross origins.

Type: Test
Uses: v_apple_song_daily (migration 142)
Depends on: a live Postgres
Persists in: nothing — the transient tenant is deleted

R235 (2026-09-27). The owner asked whether a DAILY Apple CSV would give daily Shazams.
Yes: an export of ONE day is that day's quantity, taken as is. And the old view
subtracted any two readings of a title — two exports of DIFFERENT periods (2024 then
2023) would have been subtracted as if they were two photos of one lifetime counter.
"""
from __future__ import annotations

import datetime as dt

import pytest

pytestmark = pytest.mark.xdist_group("apple-daily")


@pytest.fixture
def tenant():
    from src.database.postgres_handler import PostgresHandler
    try:
        db = PostgresHandler.from_env_or_config()
    except Exception:                                  # noqa: BLE001
        pytest.skip("no live database")
    tid = db.fetch_query(
        "INSERT INTO saas_artists (name, slug, tier, active, is_sandbox) "
        "VALUES ('R235 apple', 'r235-apple-guard', 'free', FALSE, TRUE) RETURNING id")[0][0]
    try:
        yield db, tid
    finally:
        db.execute_query("DELETE FROM apple_songs_performance WHERE artist_id = %s", (tid,))
        db.execute_query("DELETE FROM saas_artists WHERE id = %s", (tid,))
        db.close()


def _put(db, tid, day, plays, shazams, start=None, end=None):
    db.execute_query(
        "INSERT INTO apple_songs_performance (artist_id, song_name, plays, listeners, "
        "shazam_count, snapshot_date, period_start, period_end) "
        "VALUES (%s, 'Song', %s, 0, %s, %s, %s, %s)", (tid, plays, shazams, day, start, end))


def _daily(db, tid) -> dict:
    rows = db.fetch_query(
        "SELECT day, daily_plays, daily_shazams, days_since_previous FROM v_apple_song_daily "
        "WHERE artist_id = %s ORDER BY day", (tid,))
    return {r[0]: (r[1], r[2], r[3]) for r in rows}


def test_a_one_day_export_is_the_days_own_quantity(tenant) -> None:
    db, tid = tenant
    d = dt.date(2026, 5, 10)
    _put(db, tid, d, 10, 3, start=d, end=d)
    assert _daily(db, tid)[d] == (10, 3, 1)


def test_cumulative_exports_are_differenced_within_one_origin_only(tenant) -> None:
    db, tid = tenant
    o1, o2 = dt.date(2024, 1, 1), dt.date(2025, 1, 1)
    _put(db, tid, dt.date(2026, 5, 1), 100, 5, start=o1, end=dt.date(2026, 5, 1))
    _put(db, tid, dt.date(2026, 5, 2), 130, 9, start=o1, end=dt.date(2026, 5, 2))
    _put(db, tid, dt.date(2026, 5, 3), 20, 1, start=o2, end=dt.date(2026, 5, 3))
    got = _daily(db, tid)
    assert got[dt.date(2026, 5, 2)] == (30, 4, 1), "same origin: the difference"
    assert got[dt.date(2026, 5, 3)][0] is None, (
        "a reading of ANOTHER period was subtracted from the previous one")
