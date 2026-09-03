"""A SoundCloud snapshot is a DAY, not a microsecond. DB-gated.

Measured in production on 2026-08-31: one collector run wrote 19 rows for
artist 1, each carrying its own `collected_at` microsecond —
`11:00:04.101372`, `.101370`, `.101367`, … 19 rows, 19 distinct timestamps.

The weekly digest matched the snapshot with `collected_at = MAX(collected_at)`.
That predicate is true for exactly ONE row — the last track inserted. The artist
was mailed `Plays delta (7d) -21,324` against `2,229 total`, when the real totals
were 23,557 today and 23,553 a week earlier: an actual delta of **+4**.

Nothing caught it because the number was well-formed, the DAG was green, and the
week-ago half of the same query was right (it keyed on `collected_at::date`). The
two halves of one delta were computed at two different grains.

The table declares the grain itself:
    UNIQUE (artist_id, track_id, (collected_at::date))

What is pinned here is the measured REALITY — a batch whose rows carry distinct
microseconds — not the constant the fix happens to use. Seeded through the same
shape production writes, so a query that keys on the wrong column fails here.
"""
from datetime import datetime, timedelta

import pytest

from tests.db_gate import requires_live_db  # noqa: E402

pytestmark = requires_live_db()

from src.utils.digest_queries import SOUNDCLOUD_WEEKLY_DELTA_SQL  # noqa: E402

# The prod batch that exposed the defect: 19 tracks written in one run.
BATCH_SIZE = 19


@pytest.fixture
def db():
    from src.dashboard.utils import get_db_connection
    conn = get_db_connection()
    yield conn
    conn.close()


@pytest.fixture
def tenant(db):
    import uuid
    slug = f"scsnap-{uuid.uuid4().hex[:10]}"
    artist_id = db.fetch_query(
        "INSERT INTO saas_artists (name, slug, tier, active) "
        "VALUES (%s, %s, 'free', TRUE) RETURNING id", (f"SC {slug}", slug),
    )[0][0]
    yield artist_id
    db.execute_query("DELETE FROM soundcloud_tracks_daily WHERE artist_id = %s", (artist_id,))
    db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))


def _seed_batch(db, artist_id, day, plays_per_track):
    """Write one collector run: N tracks, each with its own microsecond.

    This is the shape production writes — `collected_at` is stamped per row, not
    per batch — and it is the whole reason the defect existed.
    """
    base = datetime.combine(day, datetime.min.time()) + timedelta(hours=11)
    for i, plays in enumerate(plays_per_track):
        db.execute_query(
            "INSERT INTO soundcloud_tracks_daily "
            "(track_id, title, playback_count, collected_at, artist_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (900000 + i, f"track {i}", plays,
             base + timedelta(microseconds=i * 3), artist_id),
        )


def _db_today(db):
    """The DATABASE's notion of today, never Python's.

    Measured 2026-09-04 at 00:35 local. The three tests below seeded rows at
    `datetime.now().date()` — the **local** date, Europe/Paris — while
    `SOUNDCLOUD_WEEKLY_DELTA_SQL` compares against Postgres `CURRENT_DATE`, and the
    container runs `Etc/UTC`. Between local midnight and UTC midnight the two differ
    by a day: the `week_ago` CTE looked for a snapshot `<= CURRENT_DATE - 7` =
    2026-08-27 while the fixture had seeded 2026-08-28, found nothing, and the test
    failed with `int - None`.

    So this suite went red for **two hours every night**, on a query that feeds a
    customer-facing e-mail — and a test that is red for reasons unrelated to the code
    is how a real failure gets waved through. Mixing clocks is the defect
    (`naive-datetime-now`, and `.claude/rules/python.md`: a bare `datetime.now()` is
    reserved for cosmetics that do not persist).
    """
    return db.fetch_query("SELECT CURRENT_DATE")[0][0]


def test_the_latest_total_is_the_whole_batch_not_its_last_row(db, tenant):
    """`collected_at = MAX(collected_at)` returns one track. The day returns all."""
    today = _db_today(db)
    plays = [100 + i for i in range(BATCH_SIZE)]      # 100..118
    _seed_batch(db, tenant, today, plays)

    latest, _ = db.fetch_query(SOUNDCLOUD_WEEKLY_DELTA_SQL,
                               (tenant, tenant, tenant, tenant))[0]

    assert latest == sum(plays), (
        f"the snapshot must be the whole batch ({sum(plays)} over {BATCH_SIZE} "
        f"tracks), got {latest}. A value equal to one track's playback_count "
        f"means the query keyed on `collected_at` instead of `collected_at::date`."
    )
    assert latest != plays[-1], (
        "got exactly the last-inserted track — this is the -21,324 defect verbatim"
    )


def test_a_seven_day_delta_is_not_a_fabricated_collapse(db, tenant):
    """The end-to-end number the artist reads in the mail."""
    today = _db_today(db)
    week_ago = today - timedelta(days=7)
    _seed_batch(db, tenant, week_ago, [100 + i for i in range(BATCH_SIZE)])
    _seed_batch(db, tenant, today, [101 + i for i in range(BATCH_SIZE)])

    latest, prev = db.fetch_query(SOUNDCLOUD_WEEKLY_DELTA_SQL,
                                  (tenant, tenant, tenant, tenant))[0]
    delta = latest - prev

    assert delta == BATCH_SIZE, (
        f"every track gained exactly 1 play, so the delta is {BATCH_SIZE}; got "
        f"{delta} (latest={latest}, week_ago={prev})"
    )
    assert delta > 0, "a week of growth must never render as a collapse"


def test_an_absent_snapshot_is_null_not_zero(db, tenant):
    """No history yet: the mail must read N/A, never a 0 that looks measured."""
    today = _db_today(db)
    _seed_batch(db, tenant, today, [100 + i for i in range(BATCH_SIZE)])

    latest, prev = db.fetch_query(SOUNDCLOUD_WEEKLY_DELTA_SQL,
                                  (tenant, tenant, tenant, tenant))[0]

    assert latest is not None, "today's snapshot exists and must be summed"
    assert prev is None, (
        f"there is no snapshot 7 days back, so the week-ago total must be NULL "
        f"and render as N/A; got {prev!r}. A COALESCE(...,0) here turns a missing "
        f"measurement into a full-size negative delta."
    )
