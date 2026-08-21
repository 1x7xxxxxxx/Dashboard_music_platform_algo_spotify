"""The suite must run against a database holding at least TWO tenants.

Measured 2026-08-21. A fresh canonical database (init_db.sql + every migration)
contains exactly ONE tenant — "Artist Default" — and that is what CI has always
tested against. A single-tenant database cannot expose a multi-tenant defect: with
one row, "collect for this tenant" and "collect for everyone" produce identical
results, and every isolation bug looks like correct behaviour.

Three defects found the same evening, all invisible until a second tenant existed:

  * identity-mirrored-but-written-once — the identity was written to one of the two
    places that hold it; every screen read the one that was written.
  * api-partial-date-into-date-column — the admin's own catalogue carries full
    release dates, so a year-precision album never appeared until a different
    catalogue was collected.
  * dag-conf-honoured-by-one-task-only — a per-tenant trigger spent the whole
    fleet's API quota; with one tenant in the fleet the two are the same thing.

This test is the standing guard for that condition. It is not about data volume:
two rows are enough, and one is never enough.
"""

from __future__ import annotations

import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()

MINIMUM = 2


def _tenants(db) -> list[tuple]:
    return db.fetch_query(
        "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY id")


def test_the_database_under_test_holds_at_least_two_tenants() -> None:
    from src.database.postgres_handler import PostgresHandler
    from src.utils.env_files import load_project_env

    load_project_env()
    db = PostgresHandler.from_env_or_config()
    try:
        rows = _tenants(db)
    finally:
        db.close()

    assert len(rows) >= MINIMUM, (
        f"only {len(rows)} active tenant(s) in the database under test: "
        f"{[r[1] for r in rows]}.\n"
        "A single-tenant database makes every isolation defect look correct — three "
        "were found the day this guard was written, none of them visible before.\n"
        "Fix locally:  make canary NAME=\"Canary isolation\" SPOTIFY=<public artist id>\n"
        "Fix in CI:    the seed step in .github/workflows/ci.yml"
    )


def test_the_second_tenant_is_not_a_copy_of_the_first() -> None:
    """Two rows that share an identity test nothing — that is the canary's own rule."""
    from src.database.postgres_handler import PostgresHandler
    from src.utils.env_files import load_project_env

    load_project_env()
    db = PostgresHandler.from_env_or_config()
    try:
        rows = db.fetch_query(
            "SELECT id, spotify_artist_id FROM saas_artists "
            "WHERE active = TRUE AND spotify_artist_id IS NOT NULL "
            "AND spotify_artist_id <> ''")
    finally:
        db.close()

    if len(rows) < MINIMUM:
        pytest.skip("fewer than two tenants declare a Spotify identity")

    identities = [r[1] for r in rows]
    assert len(set(identities)) == len(identities), (
        f"two tenants share a Spotify identity: {identities}. A tenant borrowing "
        "another's identity passes every isolation check while proving nothing."
    )
