"""The readiness matrix must tell the truth about ONE tenant. DB-gated.

`artist_readiness(db, artist_id)` is what the onboarding-health page, the alert
mail and now `make artist-preflight` all believe. Only its pure half was tested;
the half wired to the database — the half that decides whether an artist is told
"connected, no data" — had no test at all.

Two specific lies are pinned here:

  * a freshness check that FAILS (missing table, bad identifier) used to be
    indistinguishable from "connected but no data", so a broken probe blamed the
    artist;
  * "Spotify API" reads `artists`, a table keyed by the SPOTIFY id and not by the
    tenant, so a per-tenant call returned the whole fleet's freshness — a green
    light for someone who had never collected anything.
"""
from datetime import datetime, timedelta

import pytest

from tests.db_gate import requires_live_db  # noqa: E402

pytestmark = requires_live_db()

from src.utils.artist_readiness import (  # noqa: E402
    NO_DATA, OK, TODO, artist_readiness, readiness_red_flags,
)
from src.utils.freshness_monitor import check_freshness  # noqa: E402


@pytest.fixture
def db():
    from src.dashboard.utils import get_db_connection
    conn = get_db_connection()
    yield conn
    conn.close()


@pytest.fixture
def tenant(db):
    import uuid
    slug = f"ready-{uuid.uuid4().hex[:10]}"
    artist_id = db.fetch_query(
        "INSERT INTO saas_artists (name, slug, tier, active) "
        "VALUES (%s, %s, 'free', TRUE) RETURNING id", (f"R {slug}", slug),
    )[0][0]
    yield artist_id
    for table in ("soundcloud_tracks_daily", "artist_credentials"):
        try:
            db.execute_query(f"DELETE FROM {table} WHERE artist_id = %s", (artist_id,))
        except Exception:
            pass
    db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))


def _status(matrix, key):
    return next(row["status"] for row in matrix if row["key"] == key)


def test_new_tenant_is_todo_everywhere(db, tenant):
    """Day one: nothing declared, nothing collected — and no red herrings."""
    matrix = artist_readiness(db, tenant)

    assert {row["key"] for row in matrix}, "the matrix must not be empty"
    assert all(row["status"] == TODO for row in matrix), (
        f"a fresh tenant should be uniformly 'À connecter': "
        f"{[(r['key'], r['status']) for r in matrix]}"
    )
    assert readiness_red_flags(db, tenant) == [], "nothing is connected yet"


def test_identity_without_data_is_red_not_green(db, tenant):
    """The Benken/Grinch state: connected, and nothing arriving."""
    import json
    db.execute_query(
        "INSERT INTO artist_credentials (artist_id, platform, extra_config) "
        "VALUES (%s, 'soundcloud', %s::jsonb)",
        (tenant, json.dumps({"user_id": "123456"})),
    )

    assert _status(artist_readiness(db, tenant), "soundcloud") == NO_DATA
    assert [r["key"] for r in readiness_red_flags(db, tenant)] == ["soundcloud"]


def test_identity_with_fresh_data_is_green(db, tenant):
    import json
    db.execute_query(
        "INSERT INTO artist_credentials (artist_id, platform, extra_config) "
        "VALUES (%s, 'soundcloud', %s::jsonb)",
        (tenant, json.dumps({"user_id": "123456"})),
    )
    db.execute_query(
        "INSERT INTO soundcloud_tracks_daily (artist_id, track_id, title, collected_at) "
        "VALUES (%s, 't1', 'x', %s)", (tenant, datetime.now()),
    )

    assert _status(artist_readiness(db, tenant), "soundcloud") == OK


def test_stale_data_is_not_reported_as_missing(db, tenant):
    """Old data is a different problem from no data — and a different fix."""
    import json
    db.execute_query(
        "INSERT INTO artist_credentials (artist_id, platform, extra_config) "
        "VALUES (%s, 'soundcloud', %s::jsonb)",
        (tenant, json.dumps({"user_id": "123456"})),
    )
    db.execute_query(
        "INSERT INTO soundcloud_tracks_daily (artist_id, track_id, title, collected_at) "
        "VALUES (%s, 't1', 'x', %s)", (tenant, datetime.now() - timedelta(days=30)),
    )

    assert _status(artist_readiness(db, tenant), "soundcloud") not in (TODO, NO_DATA)


# ── freshness_monitor's own contract ────────────────────────────────────────

def test_a_failed_check_is_distinguishable_from_no_data(db, tenant):
    """A broken probe must not read as 'the artist has no data'."""
    from unittest.mock import patch

    from src.utils import freshness_monitor as fm

    broken = dict(fm.MONITOR_TARGETS[1])
    broken["table"] = "table_that_does_not_exist"
    with patch.object(fm, "MONITOR_TARGETS", [broken]):
        with patch.object(fm, "_ALLOWED_TABLES", frozenset({broken["table"]})):
            rows = check_freshness(db, tenant)

    assert rows[0]["error"], "a failing check must carry its error"
    assert rows[0]["last_dt"] is None


def test_successful_check_carries_no_error(db, tenant):
    rows = check_freshness(db, tenant)
    assert all("error" in row for row in rows), "the field must always be present"
    assert not [r for r in rows if r["error"]], (
        f"no check should fail on a provisioned schema: "
        f"{[(r['source'], r['error']) for r in rows if r['error']]}"
    )


def test_spotify_api_freshness_is_tenant_scoped(db, tenant):
    """`artists` is keyed by the Spotify id, so a per-tenant call must not read it.

    Otherwise one tenant's freshness is really the fleet's, and a brand-new
    account inherits a green light it never earned.
    """
    # Give the FLEET a fresh Spotify timestamp the tenant has no claim to. Without
    # this seed the assertion cannot fail (both sides are None on an empty DB) —
    # and a test that cannot fail proves nothing.
    db.execute_query(
        "INSERT INTO artists (artist_id, name, collected_at) VALUES (%s, %s, %s) "
        "ON CONFLICT (artist_id) DO UPDATE SET collected_at = EXCLUDED.collected_at",
        ("spotify-fleet-probe", "Fleet probe", datetime.now()),
    )
    try:
        fleet = {r["source"]: r for r in check_freshness(db)}
        mine = {r["source"]: r for r in check_freshness(db, tenant)}

        assert fleet["Spotify API"]["last_dt"] is not None, "seed did not land"
        assert mine["Spotify API"]["last_dt"] is None, (
            "a tenant with no Spotify rows must not inherit the fleet's timestamp "
            f"(fleet reports {fleet['Spotify API']['last_dt']})"
        )
    finally:
        db.execute_query("DELETE FROM artists WHERE artist_id = %s",
                         ("spotify-fleet-probe",))
