"""An all-tenants total counts the human tenants only — never the sandbox or the canary.

Type: Test
Uses: src.dashboard.utils.treasury_chart, src.dashboard.utils.kpi_helpers,
      src.dashboard.utils.revenue_forecast, src.utils.tenant_kind
Depends on: v_artist_monthly_cashflow (migration 133), a live Postgres
Persists in: nothing — the transient sandbox tenant is deleted

R220 (2026-09-27). Measured on a prod snapshot: the admin treasury « all artists » summed
the sandbox (tenant 18, a byte-for-byte mirror of artist 1) — −5 906 € for −2 833 €. The
sweep found the same gap in the ROI helpers, the admin MRR, the live pulse, the
`streamlytics_active_artists` gauge and two API routes.
"""
from __future__ import annotations

import datetime as dt

import pytest

pytestmark = pytest.mark.xdist_group("all-tenants-humans")


def _db():
    from src.database.postgres_handler import PostgresHandler
    try:
        return PostgresHandler.from_env_or_config()
    except Exception:                                  # noqa: BLE001
        pytest.skip("no live database")


@pytest.fixture
def sandbox_spend():
    """A transient SANDBOX tenant carrying 12 345 € of entered costs this month."""
    db = _db()
    row = db.fetch_query(
        "INSERT INTO saas_artists (name, slug, tier, active, is_sandbox) "
        "VALUES ('R220 sandbox', 'r220-sandbox-guard', 'free', TRUE, TRUE) RETURNING id")
    tenant = row[0][0]
    month = dt.date.today().replace(day=1)
    db.execute_query(
        "INSERT INTO artist_cost_entries (artist_id, category, amount_eur, start_month) "
        "VALUES (%s, 'promo', 12345, %s)", (tenant, month))
    try:
        yield db, tenant, month
    finally:
        db.execute_query("DELETE FROM artist_cost_entries WHERE artist_id = %s", (tenant,))
        db.execute_query("DELETE FROM saas_artists WHERE id = %s", (tenant,))
        db.close()


def test_the_admin_treasury_leaves_the_sandbox_out(sandbox_spend) -> None:
    import pandas as pd
    from src.dashboard.utils.treasury_chart import load_cashflow
    db, tenant, month = sandbox_spend
    cf = load_cashflow(db, None)
    this_month = cf[(cf["year"] == month.year) & (cf["month"] == month.month)
                    & (cf["flux"] == "depense")]
    assert not (pd.to_numeric(this_month["amount_eur"]) >= 12345).any(), (
        "the admin treasury summed a sandbox tenant's costs")


def test_the_admin_roi_leaves_the_sandbox_out(sandbox_spend) -> None:
    from src.dashboard.utils import kpi_helpers
    db, tenant, month = sandbox_spend
    fn = getattr(kpi_helpers.get_roi_data, "__wrapped__", kpi_helpers.get_roi_data)
    roi = fn(db, None, month, month)
    assert (roi["other_costs"] or 0) < 12345, "the admin ROI counted a sandbox tenant's costs"
    series = getattr(kpi_helpers.get_monthly_roi_series, "__wrapped__",
                     kpi_helpers.get_monthly_roi_series)(db, None, month, month)
    if not series.empty:
        assert (series["other_costs"].fillna(0) < 12345).all()


def test_the_detector_sees_the_defect_it_is_written_for(sandbox_spend) -> None:
    """Non-vacuity: WITHOUT the human filter, the same query does see the sandbox."""
    db, tenant, month = sandbox_spend
    raw = db.fetch_query(
        "SELECT SUM(amount_eur) FROM v_artist_monthly_cashflow "
        "WHERE flux = 'depense' AND year = %s AND month = %s AND artist_id = %s",
        (month.year, month.month, tenant))
    assert raw and float(raw[0][0] or 0) == 12345, "the fixture no longer reaches the view"
