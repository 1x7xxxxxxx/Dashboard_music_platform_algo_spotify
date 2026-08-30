"""A sandbox tenant is exempt from the identity guard — in both directions.

Type: Test
Uses: live Postgres (spotify_etl), find_identity_conflict
Depends on: migration 080 (saas_artists.is_sandbox)
Persists in: nothing — every row it writes is removed in teardown

Why the exemption exists
------------------------
To check that your own platform credentials work you must walk the onboarding from
zero and type them in. But a platform identity belongs to exactly one tenant, and
yours already belongs to your real account, so the guard refuses — correctly. That
guard is what closed the tenant leak two beta sessions were spent on; turning it off
"temporarily" is not an option, and a duplicate claim, once written, is invisible.

Migration 080 adds a third kind of tenant instead. This file pins the two halves of
its exemption, because only having one is worse than having neither:

  * a sandbox is never blocked — the point of the thing;
  * a sandbox never blocks a real tenant — otherwise a rehearsal left lying around
    would refuse a real artist their own identifier.

The canary is deliberately NOT exempt: it uses public artist ids, where a collision is
a real defect rather than an intended rehearsal.
"""
from __future__ import annotations

import os
import socket
import uuid

import pytest

_DB_HOST, _DB_PORT = "127.0.0.1", 5433


def _db_ready() -> bool:
    if not os.environ.get("DATABASE_URL"):
        try:
            with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
                pass
        except OSError:
            return False
    try:
        from src.database.postgres_handler import PostgresHandler
        db = PostgresHandler.from_env_or_config()
        try:
            db.fetch_query("SELECT is_sandbox FROM saas_artists LIMIT 1")
            return True
        finally:
            db.close()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason="needs a provisioned Postgres carrying migration 080")


@pytest.fixture()
def tenants():
    """A sandbox and a real tenant, both removed afterwards whatever happens."""
    from src.database.postgres_handler import PostgresHandler

    db = PostgresHandler.from_env_or_config()
    tag = uuid.uuid4().hex[:10]
    made: list[int] = []
    try:
        for slug, sandbox in ((f"sbx-{tag}", True), (f"real-{tag}", False)):
            made.append(db.fetch_query(
                "INSERT INTO saas_artists (name, slug, tier, active, is_sandbox) "
                "VALUES (%s, %s, 'free', TRUE, %s) RETURNING id",
                (slug, slug, sandbox))[0][0])
        yield db, made[0], made[1], f"ID{tag.upper()}"
    finally:
        for aid in made:
            db.execute_query("DELETE FROM saas_artists WHERE id = %s", (aid,))
        db.close()


def test_a_sandbox_may_claim_an_identity_a_real_tenant_holds(tenants):
    from src.dashboard.views.credentials._core import find_identity_conflict

    db, sandbox_id, real_id, value = tenants
    db.execute_query("UPDATE saas_artists SET spotify_artist_id = %s WHERE id = %s",
                     (value, real_id))

    assert find_identity_conflict(
        db, sandbox_id, "spotify", {"spotify_artist_id": value}) is None, (
        "the sandbox was refused an identity its own operator already holds. That is "
        "the exact situation migration 080 exists for: rehearsing the onboarding with "
        "real credentials, from an account that starts empty."
    )


def test_a_real_tenant_is_still_refused(tenants):
    """The exemption must not have widened into 'nobody is ever blocked'."""
    from src.dashboard.views.credentials._core import find_identity_conflict

    db, _sandbox_id, real_id, value = tenants
    db.execute_query("UPDATE saas_artists SET spotify_artist_id = %s WHERE id = %s",
                     (value, real_id))

    conflict = find_identity_conflict(
        db, real_id + 10_000_000, "spotify", {"spotify_artist_id": value})
    assert conflict is not None, (
        "a real tenant was allowed to claim an identity another real tenant holds. "
        "Two dashboards would then collect the same source and nobody could say whose "
        "numbers they are — the defect the guard was written for."
    )
    assert conflict[2] == real_id


def test_a_sandbox_never_blocks_a_real_tenant(tenants):
    """The half that is easy to forget, and worse than not having the feature."""
    from src.dashboard.views.credentials._core import find_identity_conflict

    db, sandbox_id, _real_id, value = tenants
    db.execute_query("UPDATE saas_artists SET spotify_artist_id = %s WHERE id = %s",
                     (value, sandbox_id))

    assert find_identity_conflict(
        db, sandbox_id + 10_000_000, "spotify", {"spotify_artist_id": value}) is None, (
        "a real artist was refused their own identifier because a SANDBOX held it. "
        "A rehearsal left lying around must never cost a customer their account."
    )


def test_a_canary_keeps_the_guard(tenants):
    """The exemption is granted by is_sandbox alone — never by is_canary."""
    from src.dashboard.views.credentials._core import find_identity_conflict

    db, sandbox_id, real_id, value = tenants
    db.execute_query("UPDATE saas_artists SET is_sandbox = FALSE, is_canary = TRUE "
                     "WHERE id = %s", (sandbox_id,))
    db.execute_query("UPDATE saas_artists SET spotify_artist_id = %s WHERE id = %s",
                     (value, real_id))

    assert find_identity_conflict(
        db, sandbox_id, "spotify", {"spotify_artist_id": value}) is not None, (
        "a canary was granted the sandbox exemption. The canary collects PUBLIC "
        "artists; a collision there is an accident to be reported, not a rehearsal, "
        "and widening a dangerous permission to a tenant that never asked for it is "
        "how a guard stops meaning anything."
    )
