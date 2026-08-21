"""A platform identity belongs to one tenant. Checked at save time. DB-gated.

Nothing in the schema stops two artists from declaring the same SoundCloud
user_id, YouTube channel, Meta ad account or Spotify artist. The consequence is
not cosmetic: both accounts collect the same upstream data, and
`spotify_api_daily` — which resolves a tenant by `spotify_artist_id` — cannot say
whose catalogue it is. It used to take `_sa[0][0]`, silently attributing a whole
catalogue to whichever tenant had the lower id; that was found on 2026-08-20 when
a canary tenant reused the admin's Spotify id and the E2E test attributed rows to
the wrong account.

Save time is the right moment to refuse: it is the only one where a human is
present to fix it.
"""
import json

import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()

from src.dashboard.views.credentials._core import (  # noqa: E402
    UNIQUE_IDENTITY_FIELDS, find_identity_conflict,
)


@pytest.fixture
def db():
    from src.dashboard.utils import get_db_connection
    conn = get_db_connection()
    yield conn
    conn.close()


@pytest.fixture
def two_tenants(db):
    import uuid
    ids = []
    for _ in range(2):
        slug = f"uniq-{uuid.uuid4().hex[:10]}"
        ids.append(db.fetch_query(
            "INSERT INTO saas_artists (name, slug, tier, active) "
            "VALUES (%s, %s, 'free', TRUE) RETURNING id", (f"U {slug}", slug),
        )[0][0])
    yield tuple(ids)
    for artist_id in ids:
        db.execute_query("DELETE FROM artist_credentials WHERE artist_id = %s",
                         (artist_id,))
        db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))


def _declare(db, artist_id, platform, extra):
    db.execute_query(
        "INSERT INTO artist_credentials (artist_id, platform, extra_config) "
        "VALUES (%s, %s, %s::jsonb) ON CONFLICT (artist_id, platform) "
        "DO UPDATE SET extra_config = EXCLUDED.extra_config",
        (artist_id, platform, json.dumps(extra)),
    )


@pytest.mark.parametrize("platform,field", sorted(UNIQUE_IDENTITY_FIELDS.items()))
def test_identity_already_claimed_is_refused(db, two_tenants, platform, field):
    first, second = two_tenants
    value = "shared-identity-42"
    _declare(db, first, platform, {field: value})

    conflict = find_identity_conflict(db, second, platform, {field: value})

    assert conflict is not None, f"{platform}: a duplicate {field} was accepted"
    assert conflict[0] == field
    assert conflict[2] == first, "the report must name the tenant that holds it"


@pytest.mark.parametrize("platform,field", sorted(UNIQUE_IDENTITY_FIELDS.items()))
def test_a_tenant_may_re_save_its_own_identity(db, two_tenants, platform, field):
    """Re-saving the same tab must not look like a conflict with oneself."""
    first, _second = two_tenants
    value = "my-own-identity"
    _declare(db, first, platform, {field: value})

    assert find_identity_conflict(db, first, platform, {field: value}) is None


@pytest.mark.parametrize("platform,field", sorted(UNIQUE_IDENTITY_FIELDS.items()))
def test_distinct_identities_do_not_collide(db, two_tenants, platform, field):
    first, second = two_tenants
    _declare(db, first, platform, {field: "identity-A"})

    assert find_identity_conflict(db, second, platform, {field: "identity-B"}) is None


def test_empty_identity_is_never_a_conflict(db, two_tenants):
    """An artist who saved nothing has claimed nothing."""
    first, second = two_tenants
    _declare(db, first, "soundcloud", {"user_id": ""})

    assert find_identity_conflict(db, second, "soundcloud", {"user_id": ""}) is None
    assert find_identity_conflict(db, second, "soundcloud", {}) is None


def test_spotify_conflict_is_seen_through_saas_artists(db, two_tenants):
    """Spotify's identity is mirrored onto saas_artists — the check follows it.

    `spotify_api_daily` reads `saas_artists.spotify_artist_id`, not the credentials
    row, so a conflict invisible there is a conflict the collector will meet.
    """
    first, second = two_tenants
    value = "3TVXtAsR1Inumwj472S9r4"
    db.execute_query("UPDATE saas_artists SET spotify_artist_id = %s WHERE id = %s",
                     (value, first))

    conflict = find_identity_conflict(db, second, "spotify",
                                      {"spotify_artist_id": value})

    assert conflict is not None, "a duplicate Spotify artist id was accepted"
    assert conflict[2] == first


def test_every_identity_is_typable_in_a_real_tab():
    """Each identity's field must exist in the tab that stores it.

    This used to assert `set(UNIQUE_IDENTITY_FIELDS) == set(PLATFORMS)` — identities
    and TABS being the same set. They are not: there are five identities and four
    tabs, because Instagram's id is a field of the Meta tab. Insisting on equality is
    exactly what kept `instagram` out of the uniqueness map, and with it out of
    `find_identity_conflict`: two tenants could claim the same Instagram account and
    nothing refused.
    """
    from src.dashboard.views.credentials._registry import PLATFORMS
    from src.utils.tenant_identity import PLATFORM_IDENTITIES

    for logical, spec in PLATFORM_IDENTITIES.items():
        assert spec.storage in PLATFORMS, (
            f"{logical} is stored under '{spec.storage}', which is not a tab"
        )
        keys = {f["key"] for f in PLATFORMS[spec.storage]["fields"]}
        assert spec.field in keys, (
            f"{logical}'s identity '{spec.field}' has no input in the "
            f"'{spec.storage}' tab — no artist could ever declare it"
        )
        assert logical in UNIQUE_IDENTITY_FIELDS, (
            f"{logical} has no uniqueness rule — two tenants could claim the same one"
        )
