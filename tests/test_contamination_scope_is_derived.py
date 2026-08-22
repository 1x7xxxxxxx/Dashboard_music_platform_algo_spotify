"""The contamination check must know about every tenant-scoped table, or say why not.

Installed 2026-08-22 (R27). `tenant_contamination_check.py` is step 5 of
`make artist-preflight` — the step whose whole claim is "no row under this tenant
belongs to somebody else". It was making that claim about eight tables, typed by
hand, out of the seventy-odd the schema carries. Five of the eight had no platform
identifier, so only the weaker ORPHAN half applied to them, and there was no Spotify
entry at all — although `tracks` stores the Spotify artist id right next to the
tenant, which is the strongest comparison available anywhere in the schema.

The tool now derives its table set from `information_schema` by platform prefix. This
test is the other half of that: a tenant-scoped table must be claimed by a platform
or listed in `_OUT_OF_SCOPE` with a reason. Adding `meta_insights_something_new`
without touching the tool is then fine — the prefix picks it up. Adding a table for a
platform nobody thought of fails here, loudly, on the day it is created.

This is the same class the night of 2026-08-21→22 had already produced twice: a guard
whose reach is a list somebody remembered to update.
"""
import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()


@pytest.fixture(scope="module")
def db():
    from src.dashboard.utils import get_db_connection

    conn = get_db_connection()
    yield conn
    conn.close()


def test_every_tenant_scoped_table_is_claimed_or_excused(db):
    from tools.tenant_contamination_check import (
        _OUT_OF_SCOPE, platform_of, tenant_scoped_tables,
    )

    scoped = tenant_scoped_tables(db)
    assert len(scoped) > 30, (
        f"only {len(scoped)} tenant-scoped tables found — the schema probe is not "
        "reading the live database, and every assertion here is true of nothing"
    )

    unclaimed = sorted(t for t in scoped
                       if platform_of(t) is None and t not in _OUT_OF_SCOPE)
    assert not unclaimed, (
        f"{unclaimed} carry a tenant column and are neither owned by a platform "
        "prefix nor listed in _OUT_OF_SCOPE.\n"
        "Step 5 of `make artist-preflight` says no row under a tenant belongs to "
        "someone else. It can only say that about tables it looks at. Either give "
        "the table's platform a prefix that matches it, or add it to _OUT_OF_SCOPE "
        "with the reason it cannot be contaminated."
    )


def test_out_of_scope_entries_carry_a_reason():
    """An excuse with no reason is a list of tables somebody wanted to stop seeing."""
    from tools.tenant_contamination_check import _OUT_OF_SCOPE

    empty = sorted(t for t, why in _OUT_OF_SCOPE.items() if not (why or "").strip())
    assert not empty, f"{empty} are excluded with no reason given"


def test_out_of_scope_does_not_name_tables_that_no_longer_exist(db):
    """A stale exclusion silently protects nothing and hides that it is stale."""
    from tools.tenant_contamination_check import _OUT_OF_SCOPE, tenant_scoped_tables

    existing = set(tenant_scoped_tables(db))
    # A table can also legitimately have lost its tenant column; check existence.
    all_tables = {r[0] for r in db.fetch_query(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")}
    ghosts = sorted(t for t in _OUT_OF_SCOPE if t not in all_tables)
    assert not ghosts, (
        f"{ghosts} are excluded from the contamination check but no longer exist. "
        "Remove them, or the list stops describing the schema."
    )
    assert existing, "no tenant-scoped table found at all"


def test_the_platforms_that_fetch_under_a_tenant_identity_are_all_covered():
    """Every platform with a per-tenant credential must have a contamination entry.

    The Spotify gap was invisible because nothing compared the two lists. This is
    that comparison: the identity fields the credentials layer knows about, against
    the platforms this tool scans.
    """
    from tools.tenant_contamination_check import _PLATFORMS

    # Platforms whose collection uses an identity belonging to the ARTIST, not to the
    # admin's central app (ADR-006). Those are exactly the ones whose rows can end up
    # under the wrong tenant.
    expected = {"youtube", "instagram", "soundcloud", "meta", "spotify"}
    missing = sorted(expected - set(_PLATFORMS))
    assert not missing, (
        f"{missing} collect under a per-tenant identity and are not checked for "
        "contamination. Spotify was missing from 2026-08 until R27, while `tracks` "
        "is the one table that pins a platform id against the tenant that holds it."
    )


def test_the_scan_returns_findings_shaped_the_way_the_preflight_reads_them(db):
    """`artist_preflight.step_contamination` filters on `artist_id`; keep that key."""
    from tools.tenant_contamination_check import scan

    for finding in scan(db):
        assert {"artist_id", "table", "kind", "rows", "detail"} <= set(finding), (
            f"a finding is missing keys the preflight reads: {finding}"
        )
