"""The fleet readiness costs a bounded number of queries PER TENANT (R266 e, ADR-030).

`views/onboarding_health.py` computed `artist_readiness` once per tenant: ~14 queries
each — identities, Spotify id, then one freshness query per monitored source. At fifty
tenants that is ~700 queries for one render. `readiness_many` reads identities, Spotify
ids and every source's freshness ONCE for the whole fleet (`ANY(%s) GROUP BY`).

What still grows with the fleet, and why it is bounded: the two « expected silence »
rules (no Meta campaign running, no S4A release since the last import) are asked only
for a STALE source, per tenant, because their answer depends on that tenant's own
declared account. That is at most `_SILENCE_SLOPE` queries per tenant.

Does not cover: `render_status_matrix`'s own per-tenant reads (probes, identities), which
the page still pays once per expanded tenant.
"""
from __future__ import annotations

import uuid

import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()

_SILENCE_SLOPE = 3          # measured 2026-09-28: 14 queries for 1 tenant, 50 for 13
_PER_TENANT_BEFORE = 14


@pytest.fixture
def db():
    from src.dashboard.utils import get_db_connection
    conn = get_db_connection()
    yield conn
    conn.close()


@pytest.fixture
def tenants(db):
    ids = []
    for _ in range(10):
        slug = f"fleet-{uuid.uuid4().hex[:10]}"
        ids.append(db.fetch_query(
            "INSERT INTO saas_artists (name, slug, tier, active) "
            "VALUES (%s, %s, 'free', TRUE) RETURNING id", (f"F {slug}", slug))[0][0])
    yield ids
    db.execute_query("DELETE FROM saas_artists WHERE id = ANY(%s)", (ids,))


def _count(db, fn) -> int:
    n = [0]
    for name in ("fetch_query", "fetch_df"):
        real = getattr(db, name)

        def counted(*a, _real=real, **k):
            n[0] += 1
            return _real(*a, **k)
        setattr(db, name, counted)
    try:
        fn()
    finally:
        for name in ("fetch_query", "fetch_df"):
            delattr(db, name)
    return n[0]


def test_the_fleet_readiness_does_not_grow_with_tenants(db, tenants):
    from src.utils.artist_readiness import readiness_many
    one = _count(db, lambda: readiness_many(db, tenants[:1]))
    ten = _count(db, lambda: readiness_many(db, tenants))
    slope = (ten - one) / 9
    assert slope <= _SILENCE_SLOPE, (
        f"{one} queries for 1 tenant, {ten} for 10: {slope:.1f} per extra tenant "
        f"(bound {_SILENCE_SLOPE}; the per-tenant path cost {_PER_TENANT_BEFORE})")


def test_the_batch_says_what_the_per_tenant_read_says(db, tenants):
    from src.utils.artist_readiness import artist_readiness, readiness_many
    batch = readiness_many(db, tenants[:3])
    for aid in tenants[:3]:
        assert [(r["key"], r["status"], r["next_action"]) for r in batch[aid]] == \
               [(r["key"], r["status"], r["next_action"]) for r in artist_readiness(db, aid)]
