"""The contamination detector must actually detect. Read-only, DB-gated.

`tools/tenant_contamination_check.py` is what tells you how much of production is
already wrong before anything is deleted. A detector that reports "clean" on a
contaminated database is worse than none: it authorises inviting the next artist.

These tests plant each contamination shape deliberately and assert it is found —
and that a correctly-owned row is not.
"""

import pytest

from tests.db_gate import requires_live_db  # noqa: E402

pytestmark = requires_live_db()

from tools.tenant_contamination_check import scan  # noqa: E402


@pytest.fixture
def db():
    from src.dashboard.utils import get_db_connection
    conn = get_db_connection()
    yield conn
    conn.close()


@pytest.fixture
def tenant(db):
    import uuid
    slug = f"contam-{uuid.uuid4().hex[:10]}"
    artist_id = db.fetch_query(
        "INSERT INTO saas_artists (name, slug, tier, active) "
        "VALUES (%s, %s, 'free', TRUE) RETURNING id", (f"C {slug}", slug),
    )[0][0]
    yield artist_id
    for table in ("youtube_videos", "youtube_channels", "youtube_video_stats",
                  "instagram_daily_stats", "soundcloud_tracks_daily",
                  "artist_credentials"):
        try:
            db.execute_query(f"DELETE FROM {table} WHERE artist_id = %s", (artist_id,))
        except Exception:
            pass
    db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))


def _connect_platform(db, artist_id, platform, extra):
    import json
    db.execute_query(
        "INSERT INTO artist_credentials (artist_id, platform, extra_config) "
        "VALUES (%s, %s, %s::jsonb) ON CONFLICT (artist_id, platform) "
        "DO UPDATE SET extra_config = EXCLUDED.extra_config",
        (artist_id, platform, json.dumps(extra)),
    )


def _findings_for(db, artist_id):
    return [f for f in scan(db) if f["artist_id"] == artist_id]


def test_rows_for_a_platform_the_tenant_never_connected_are_flagged(db, tenant):
    """ORPHAN: collection is impossible without an identity, so these came from
    someone else's — the shape both beta testers hit."""
    db.execute_query(
        "INSERT INTO soundcloud_tracks_daily (artist_id, track_id, title, collected_at) "
        "VALUES (%s, 'trk-1', 'Not mine', CURRENT_DATE)", (tenant,))

    kinds = {f["kind"] for f in _findings_for(db, tenant)}
    assert "ORPHAN" in kinds


def test_row_carrying_another_channel_id_is_flagged_and_names_the_owner(db, tenant):
    """MISMATCH is the strongest evidence: it prints whose data it really is."""
    _connect_platform(db, tenant, "youtube", {"channel_id": "UCmine0000000000000"})
    db.execute_query(
        "INSERT INTO youtube_videos (artist_id, video_id, channel_id, title) "
        "VALUES (%s, 'vid-x', 'UCadmin000000000000', 'Admin video')", (tenant,))

    findings = [f for f in _findings_for(db, tenant) if f["kind"] == "MISMATCH"]
    assert findings, "a video from another channel was not detected"
    assert "UCadmin000000000000" in findings[0]["detail"]


def test_correctly_owned_rows_are_not_flagged(db, tenant):
    """No false positive, or the report gets ignored — and then so do the real ones."""
    _connect_platform(db, tenant, "youtube", {"channel_id": "UCmine0000000000000"})
    db.execute_query(
        "INSERT INTO youtube_videos (artist_id, video_id, channel_id, title) "
        "VALUES (%s, 'vid-ok', 'UCmine0000000000000', 'Mine')", (tenant,))

    assert [f for f in _findings_for(db, tenant) if f["table"] == "youtube_videos"] == []


def test_instagram_identity_is_read_from_the_meta_row(db, tenant):
    """Instagram has no credentials row of its own — it rides `meta.ig_user_id`."""
    _connect_platform(db, tenant, "meta", {"account_id": "act_1", "ig_user_id": "17841"})
    db.execute_query(
        "INSERT INTO instagram_daily_stats (artist_id, ig_user_id, username, collected_at) "
        "VALUES (%s, '17841', 'me', CURRENT_DATE)", (tenant,))

    ig = [f for f in _findings_for(db, tenant) if f["table"] == "instagram_daily_stats"]
    assert ig == [], f"correctly-owned Instagram rows were flagged: {ig}"


def test_scan_never_writes(db, tenant):
    """It runs against production. It reads."""
    _connect_platform(db, tenant, "youtube", {"channel_id": "UCmine0000000000000"})
    db.execute_query(
        "INSERT INTO youtube_videos (artist_id, video_id, channel_id, title) "
        "VALUES (%s, 'vid-count', 'UCadmin000000000000', 'x')", (tenant,))

    before = db.fetch_query(
        "SELECT COUNT(*) FROM youtube_videos WHERE artist_id = %s", (tenant,))[0][0]
    scan(db)
    after = db.fetch_query(
        "SELECT COUNT(*) FROM youtube_videos WHERE artist_id = %s", (tenant,))[0][0]
    assert before == after
