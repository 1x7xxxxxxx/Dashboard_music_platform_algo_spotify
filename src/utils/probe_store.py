"""The memory of the last platform probe verdict, per tenant.

Type: Utility
Uses: tenant_platform_probe
Depends on: nothing under src/dashboard
Persists in: tenant_platform_probe (one row per artist × platform, overwritten)

Moved from `src/dashboard/utils/status_matrix.py` (R626): the nightly `alert_monitor`
DAG writes the same verdicts, and importing the dashboard's status matrix to do it put
an Airflow task on top of a Streamlit layer. The matrix re-imports the name.
"""
from __future__ import annotations


def save_probe(db, artist_id: int, platform: str, ok: bool, reason: str,
               category: str | None = None) -> None:
    """Remember one verdict. Overwrites — we want the latest, not a history."""
    db.execute_query(
        "INSERT INTO tenant_platform_probe "
        "  (artist_id, platform, ok, reason, category, probed_at) "
        "VALUES (%s, %s, %s, %s, %s, now()) "
        "ON CONFLICT (artist_id, platform) DO UPDATE SET "
        "  ok = EXCLUDED.ok, reason = EXCLUDED.reason, "
        "  category = EXCLUDED.category, probed_at = EXCLUDED.probed_at",
        (artist_id, platform, bool(ok), (reason or "")[:500], category))
