"""An artist released under a label must still be able to see their numbers.

Installed 2026-08-22, the GRiNCH case. His SoundCloud identity is correct and resolves
to his real profile; that profile has `track_count=0`, because everything he releases
comes out under other accounts. There was nothing to collect and every surface told
him to check his User ID — the one thing that was already right.

Measured against the API the same day: `GET /tracks/{id}` returns `playback_count`,
`reposts_count` and `comment_count` for a track whatever profile hosts it (1027 plays
on a third party's upload). So the collectable unit for such an artist is the TRACK,
not the profile.

Nothing new is stored: `track_platform_link.platform_ref_id` already means "the id of
this track on this platform". What migration 074 adds is the guard — two artists on
one label would otherwise each claim the same upload and each collect the other's
plays under their own `artist_id`, which is `identity-claimed-by-two-tenants` moved
one level down.
"""
from __future__ import annotations

import uuid

import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()


@pytest.fixture
def two_tenants():
    from src.dashboard.utils import get_db_connection

    db = get_db_connection()
    ids = []
    for _ in range(2):
        slug = f"claim-{uuid.uuid4().hex[:10]}"
        ids.append(db.fetch_query(
            "INSERT INTO saas_artists (name, slug, tier, active) "
            "VALUES (%s, %s, 'free', TRUE) RETURNING id", (slug, slug))[0][0])
    db.close()
    yield ids
    db = get_db_connection()
    for artist_id in ids:
        db.execute_query("DELETE FROM track_platform_link WHERE artist_id = %s",
                         (artist_id,))
        db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))
    db.close()


def test_a_declared_track_is_readable_back(two_tenants):
    from src.dashboard.utils import get_db_connection
    from src.utils.claimed_tracks import claim_track, claimed_track_ids

    owner, _ = two_tenants
    db = get_db_connection()
    try:
        claim_track(db, owner, "soundcloud", "2212442699", "Boogie Dance")
        assert claimed_track_ids(db, owner, "soundcloud") == ["2212442699"]
    finally:
        db.close()


def test_claiming_twice_is_a_no_op(two_tenants):
    """Re-saving the form must not create a duplicate or refuse the owner."""
    from src.dashboard.utils import get_db_connection
    from src.utils.claimed_tracks import claim_track, claimed_track_ids

    owner, _ = two_tenants
    db = get_db_connection()
    try:
        claim_track(db, owner, "soundcloud", "2212442699", "Boogie Dance")
        claim_track(db, owner, "soundcloud", "2212442699", "Boogie Dance")
        assert claimed_track_ids(db, owner, "soundcloud") == ["2212442699"]
    finally:
        db.close()


def test_a_second_tenant_cannot_claim_the_same_track(two_tenants):
    """The whole reason the guard exists: two artists on one label."""
    from src.dashboard.utils import get_db_connection
    from src.utils.claimed_tracks import TrackAlreadyClaimedError, claim_track

    owner, other = two_tenants
    db = get_db_connection()
    try:
        claim_track(db, owner, "soundcloud", "2212442699", "Boogie Dance")
        with pytest.raises(TrackAlreadyClaimedError):
            claim_track(db, other, "soundcloud", "2212442699", "Boogie Dance")
    finally:
        db.close()


def test_the_database_refuses_it_too(two_tenants):
    """The code check is the message; the index is the backstop.

    A second writer — a script, a migration, direct SQL — must not be able to do what
    `claim_track` refuses. That asymmetry is how `identity-claimed-by-two-tenants`
    happened in the first place.
    """
    import psycopg2

    from src.dashboard.utils import get_db_connection
    from src.utils.claimed_tracks import claim_track

    owner, other = two_tenants
    db = get_db_connection()
    try:
        claim_track(db, owner, "soundcloud", "2212442699", "Boogie Dance")
        with pytest.raises(psycopg2.errors.UniqueViolation):
            db.execute_query(
                "INSERT INTO track_platform_link (artist_id, match_key, platform, "
                "platform_title, platform_ref_id, status, confidence, method) "
                "VALUES (%s, 'x', 'soundcloud', 'X', '2212442699', 'confirmed', 1.0, "
                "'manual')", (other,))
    finally:
        db.close()


def test_a_rejected_suggestion_does_not_block_a_claim(two_tenants):
    """The index is partial on purpose: the suggester proposes before anyone arbitrates."""
    from src.dashboard.utils import get_db_connection
    from src.utils.claimed_tracks import claim_track

    owner, other = two_tenants
    db = get_db_connection()
    try:
        db.execute_query(
            "INSERT INTO track_platform_link (artist_id, match_key, platform, "
            "platform_title, platform_ref_id, status, confidence, method) "
            "VALUES (%s, 'x', 'soundcloud', 'X', '2212442699', 'rejected', 0.4, "
            "'title+date')", (other,))
        claim_track(db, owner, "soundcloud", "2212442699", "Boogie Dance")
    finally:
        db.close()


def test_releasing_a_claim_frees_the_track(two_tenants):
    from src.dashboard.utils import get_db_connection
    from src.utils.claimed_tracks import claim_track, claimed_track_ids, release_claim

    owner, other = two_tenants
    db = get_db_connection()
    try:
        claim_track(db, owner, "soundcloud", "2212442699", "Boogie Dance")
        release_claim(db, owner, "soundcloud", "2212442699")
        assert claimed_track_ids(db, owner, "soundcloud") == []
        claim_track(db, other, "soundcloud", "2212442699", "Boogie Dance")
    finally:
        db.close()


def test_only_a_track_url_is_accepted():
    """A profile URL has one path segment, a track URL has two.

    Pasting the profile is the obvious mistake for an artist who has just been told
    their profile is not the answer.
    """
    from src.utils.claimed_tracks import is_soundcloud_track_url

    assert is_soundcloud_track_url("https://soundcloud.com/benken50cl/boogie-dance")
    assert not is_soundcloud_track_url("https://soundcloud.com/grinchhh")
    assert not is_soundcloud_track_url("")
    assert not is_soundcloud_track_url("https://spotify.com/track/x/y")


def test_the_collector_asks_for_the_claimed_tracks(two_tenants, monkeypatch):
    """The collector must actually read the claims — not just the profile."""
    from src.dashboard.utils import get_db_connection
    from src.collectors.soundcloud_api_collector import SoundCloudCollector
    from src.utils.claimed_tracks import claim_track

    owner, _ = two_tenants
    db = get_db_connection()
    try:
        claim_track(db, owner, "soundcloud", "2212442699", "Boogie Dance")

        collector = SoundCloudCollector.__new__(SoundCloudCollector)
        collector.artist_id = owner
        collector.db = db
        collector._access_token = "tok"
        collector._token_expires_at = 9e18
        asked = []

        class _Resp:
            status_code = 200

            @staticmethod
            def json():
                return {"id": 2212442699, "title": "Boogie Dance",
                        "permalink_url": "https://soundcloud.com/x/y",
                        "playback_count": 1027, "reposts_count": 6,
                        "comment_count": 0, "created_at": None}

        class _Session:
            def get(self, url, **kw):
                asked.append(url)
                return _Resp()

        collector.session = _Session()
        monkeypatch.setattr(collector, "_ensure_token", lambda: None)

        rows = collector.fetch_claimed_tracks()
        assert any("/tracks/2212442699" in u for u in asked), (
            f"the collector never asked for the declared track: {asked}"
        )
        assert len(rows) == 1 and rows[0]["playback_count"] == 1027
        assert rows[0]["artist_id"] == owner, "the row landed under the wrong tenant"
    finally:
        db.close()


def test_a_track_already_seen_on_the_profile_is_not_collected_twice(two_tenants):
    from src.dashboard.utils import get_db_connection
    from src.collectors.soundcloud_api_collector import SoundCloudCollector
    from src.utils.claimed_tracks import claim_track

    owner, _ = two_tenants
    db = get_db_connection()
    try:
        claim_track(db, owner, "soundcloud", "2212442699", "Boogie Dance")
        collector = SoundCloudCollector.__new__(SoundCloudCollector)
        collector.artist_id = owner
        collector.db = db
        assert collector.fetch_claimed_tracks(already={"2212442699"}) == []
    finally:
        db.close()
