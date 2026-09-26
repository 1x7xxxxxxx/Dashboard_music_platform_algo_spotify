"""A monitored table that EXISTS and holds no row for a tenant is a collection gap.

Type: Test
Uses: src/utils/freshness_monitor.check_freshness, src/utils/monitoring_checks.tenant_freshness_gaps
Depends on: nothing (the database is a stub answering the one question asked)
Persists in: nothing

Error class `collector-shipped-dag-not-rerun`. On 2026-05-15 a collector and its table
shipped (migration applied, `src/` volume-mounted, so the code was live at once) while
the owning DAG had last run BEFORE the ship — the table stayed empty and the view said
« no data », which read as a bug. The catalogue's signature asks the database « does the
table exist AND hold zero rows? »; that query needs a live Postgres and names one table.

The automatic half of that question lives in the nightly freshness chain:
`check_freshness` reads `MAX(<column>)` per tenant, and an existing table with no row
answers `NULL` — which must come out `stale=True` with NO `error` (the table is there,
the collection is not), and `tenant_freshness_gaps` must then name that tenant's
declared platform in the nightly mail. A missing table is the other state (`error`
set) and is guarded by `test_broken_probe_is_not_the_artists_fault.py`.

Does NOT cover: a table outside `MONITOR_TARGETS` (e.g. `instagram_media`, the original
site — the monitor reads the platform's follower table, not every table it owns); a
platform the tenant never declared (suppressed on purpose); a table FULL but stale
since the ship, which is the ordinary staleness threshold.
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.utils.freshness_monitor import check_freshness
from src.utils.monitoring_checks import tenant_freshness_gaps

_TENANT = 7


class _StubDB:
    """Answers `SELECT MAX(col), age FROM <table>` with one fixed row; nothing else."""

    def __init__(self, newest: tuple) -> None:
        self._newest = newest

    def fetch_query(self, sql: str, params: tuple = ()) -> list:
        return [self._newest] if sql.startswith("SELECT MAX(") else []


def collection_gaps(newest: tuple, declared: set[str]) -> list[dict]:
    """The nightly chain for ONE tenant, over a database whose tables all answer `newest`."""
    rows = check_freshness(_StubDB(newest), _TENANT)
    return tenant_freshness_gaps([(_TENANT, "Tenant", rows)], {_TENANT: declared})


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Shipped, not re-run: every table exists and is empty → the declared platform is
    a gap, and the probe did not fail. Re-run: one fresh row → no gap."""
    empty = check_freshness(_StubDB((None, None)), _TENANT)
    instagram = [r for r in empty if r["source"] == "Instagram"]
    assert instagram and instagram[0]["stale"] and instagram[0]["error"] is None, instagram

    assert collection_gaps((None, None), {"instagram"}) == [
        {"artist_id": _TENANT, "artist_name": "Tenant", "stale_sources": ["Instagram"]}]

    fresh = (datetime.now(timezone.utc), 1.0)
    assert collection_gaps(fresh, {"instagram"}) == []
