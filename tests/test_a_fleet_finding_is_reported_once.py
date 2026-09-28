"""A fleet-wide contamination finding comes out ONCE, and the sandbox is not an incident.

R285 — the 2026-09-28 ops mail listed the same MISATTRIBUTED line eight times: the two
fleet-wide JOIN checks (`track_popularity_history` ↔ `tracks`, `youtube_video_stats` ↔
`youtube_videos`) ran inside the per-tenant loop without a tenant filter, so each tenant
scanned re-emitted the whole fleet's findings, and the subject's count grew with the
fleet. And the sandbox, a designed mirror of artist 1 (migration 080), made
« CONTAMINATION » the subject of every night.

Does not cover: the ORPHAN/MISMATCH half, which is per tenant by construction (its SQL
filters on the tenant column) — `tests/test_tenant_contamination_check.py` plants those.
"""
from __future__ import annotations

import tools.tenant_contamination_check as tc


class _FakeDb:
    """Three tenants, one misattributed popularity row, tenant 18 is the sandbox."""

    def fetch_query(self, sql, params=None):
        if "FROM saas_artists ORDER BY id" in sql:
            return [(1, "A"), (12, "B"), (18, "Sandbox")]
        if "is_sandbox" in sql:
            return [(18,)]
        if "FROM track_popularity_history h" in sql:
            return [(18, 1, 40)]
        return []


def _scan(monkeypatch):
    monkeypatch.setattr(tc, "_declared_identities", lambda db: {})
    monkeypatch.setattr(tc, "tenant_scoped_tables", lambda db: {
        "track_popularity_history": "artist_id", "tracks": "saas_artist_id"})
    monkeypatch.setattr(tc, "platform_of", lambda table: None)
    return tc.scan(_FakeDb())


def test_a_fleet_misattribution_is_reported_once(monkeypatch):
    found = [f for f in _scan(monkeypatch) if f["kind"] == "MISATTRIBUTED"]
    assert len(found) == 1, (
        f"{len(found)} copies of one fleet-wide finding — the JOIN runs once per tenant "
        "scanned (R285)")


def test_the_sandbox_finding_is_expected_not_an_incident(monkeypatch):
    found = _scan(monkeypatch)
    assert found and all(f["expected"] for f in found if f["artist_id"] == 18)
    assert tc._mark_expected([{"artist_id": 12}], {18})[0]["expected"] is None, (
        "a real tenant's finding must stay an incident")
