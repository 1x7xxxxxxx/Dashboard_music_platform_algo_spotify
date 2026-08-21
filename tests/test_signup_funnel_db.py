"""Creating an artist account, end to end, against the real schema. DB-gated.

Every beta session starts here, and nothing tested it: `_create_artist_and_user`
had no coverage at all, `register` was absent from the render-smoke list, and the
first thing anyone knew about a broken signup was a person sitting in front of it.

What is pinned:
  * the pair (saas_users, saas_artists) is created atomically and linked;
  * the account starts UNVERIFIED with a token, and verification flips exactly
    that flag;
  * the fresh tenant is COHERENT for everything downstream — no identity, no data,
    no contamination, and a readiness matrix that says "à connecter" rather than
    inventing a green light.
"""
import uuid

import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()

from src.dashboard.views.register import _create_artist_and_user  # noqa: E402


@pytest.fixture
def db():
    from src.dashboard.utils import get_db_connection
    conn = get_db_connection()
    yield conn
    conn.close()


@pytest.fixture
def signup(db):
    """Create an account the way the register form does, and clean it up after."""
    created = {}
    suffix = uuid.uuid4().hex[:10]
    user_id, artist_id = _create_artist_and_user(
        db,
        artist_name=f"Funnel {suffix}", slug=f"funnel-{suffix}",
        username=f"user_{suffix}", email=f"{suffix}@example.test",
        pw="a-long-enough-password", token=f"tok-{suffix}",
    )
    created.update(user_id=user_id, artist_id=artist_id,
                   token=f"tok-{suffix}", suffix=suffix)
    yield created
    db.execute_query("DELETE FROM artist_credentials WHERE artist_id = %s", (artist_id,))
    db.execute_query("DELETE FROM saas_users WHERE id = %s", (user_id,))
    db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))


def test_signup_creates_a_linked_user_and_tenant(db, signup):
    rows = db.fetch_query(
        "SELECT u.artist_id, u.role, u.active, u.email_verified, a.tier, a.active "
        "FROM saas_users u JOIN saas_artists a ON a.id = u.artist_id WHERE u.id = %s",
        (signup["user_id"],),
    )
    assert rows, "the CTE did not produce a linked pair"
    artist_id, role, user_active, verified, tier, artist_active = rows[0]

    assert artist_id == signup["artist_id"]
    assert role == "artist", "a signup must never create an admin"
    assert user_active and artist_active
    assert verified is False, "an account starts unverified"
    assert tier == "free"


def test_the_verification_token_is_stored_and_usable(db, signup):
    rows = db.fetch_query(
        "SELECT verification_token FROM saas_users WHERE id = %s", (signup["user_id"],))
    assert rows[0][0] == signup["token"]

    # What the verification link does.
    db.execute_query(
        "UPDATE saas_users SET email_verified = TRUE, verification_token = NULL "
        "WHERE verification_token = %s", (signup["token"],))
    verified, token = db.fetch_query(
        "SELECT email_verified, verification_token FROM saas_users WHERE id = %s",
        (signup["user_id"],))[0]
    assert verified is True and token is None


def test_the_password_is_not_stored_in_clear(db, signup):
    stored = db.fetch_query(
        "SELECT password_hash FROM saas_users WHERE id = %s", (signup["user_id"],))[0][0]
    assert stored and "a-long-enough-password" not in stored


def test_a_fresh_tenant_owns_no_rows_anywhere(db, signup):
    """Day one means day one — a new account inherits nothing from anyone."""
    from tools.tenant_contamination_check import scan

    findings = [f for f in scan(db) if f["artist_id"] == signup["artist_id"]]
    assert findings == [], f"a brand-new tenant already owns rows: {findings}"


def test_a_fresh_tenant_reads_as_to_be_connected(db, signup):
    """Not green, not red — the honest state is 'nothing declared yet'."""
    from src.utils.artist_readiness import TODO, artist_readiness

    matrix = artist_readiness(db, signup["artist_id"])
    assert matrix, "the readiness matrix must not be empty"
    assert all(row["status"] == TODO for row in matrix), (
        f"{[(r['key'], r['status']) for r in matrix]}"
    )


def test_two_signups_get_distinct_tenants(db, signup):
    """Obvious, and worth pinning: the slug is unique, the tenant must be too."""
    suffix = uuid.uuid4().hex[:10]
    user_id, artist_id = _create_artist_and_user(
        db,
        artist_name=f"Funnel {suffix}", slug=f"funnel-{suffix}",
        username=f"user_{suffix}", email=f"{suffix}@example.test",
        pw="another-long-password", token=f"tok-{suffix}",
    )
    try:
        assert artist_id != signup["artist_id"]
        assert user_id != signup["user_id"]
    finally:
        db.execute_query("DELETE FROM saas_users WHERE id = %s", (user_id,))
        db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))


def test_a_duplicate_slug_is_rejected(db, signup):
    """The tenant key is the slug; two accounts sharing one would share a URL."""
    import psycopg2

    with pytest.raises(psycopg2.Error):
        _create_artist_and_user(
            db,
            artist_name="Clash", slug=f"funnel-{signup['suffix']}",
            username=f"other_{uuid.uuid4().hex[:8]}",
            email=f"{uuid.uuid4().hex[:8]}@example.test",
            pw="yet-another-password", token="tok-clash",
        )
