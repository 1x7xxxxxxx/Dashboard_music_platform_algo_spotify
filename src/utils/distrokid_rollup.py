"""Roll up distrokid_sales_detail (USD) into distrokid_monthly_revenue (EUR).

Type: Utility
Uses: PostgresHandler.execute_query
Triggers: called by the CSV import (upload_csv) and the distrokid_csv_watcher DAG
Persists in: distrokid_monthly_revenue (source='import' rows only)
Depends on: distrokid_sales_detail, distrokid_monthly_revenue

Mirror of imusician_rollup.py with one twist: DistroKid pays in USD while the
whole dashboard (Distributeur view, ROI helpers) is EUR. The roll-up applies an
explicit USD→EUR rate — passed by the caller (Upload CSV input field) or read
from DISTROKID_USD_EUR_RATE (default 0.92). The rate is persisted on each row
(fx_rate column, migration 059) so revenue_eur stays reversible to USD; the
prose notes keep it human-readable too. Manual entries (source != 'import')
keep fx_rate NULL and are never overwritten.
"""
import os

_ROLLUP_SQL = """
    INSERT INTO distrokid_monthly_revenue
        (artist_id, year, month, revenue_eur, fx_rate, source, notes, updated_at)
    SELECT artist_id, sale_year, sale_month,
           ROUND((SUM(earnings_usd) * %s)::numeric, 2),
           %s,
           'import',
           'Agrégé automatiquement depuis l''import DistroKid (taux USD→EUR ' || %s || ')',
           CURRENT_TIMESTAMP
    FROM distrokid_sales_detail
    WHERE artist_id = %s
    GROUP BY artist_id, sale_year, sale_month
    ON CONFLICT (artist_id, year, month) DO UPDATE
        SET revenue_eur = EXCLUDED.revenue_eur,
            fx_rate = EXCLUDED.fx_rate,
            notes = EXCLUDED.notes,
            source = 'import',
            updated_at = CURRENT_TIMESTAMP
        WHERE distrokid_monthly_revenue.source = 'import'
"""


def default_fx_rate() -> float:
    """USD→EUR rate from DISTROKID_USD_EUR_RATE, default 0.92."""
    try:
        return float(os.getenv('DISTROKID_USD_EUR_RATE', '0.92'))
    except ValueError:
        return 0.92


def rollup_sales_to_monthly(db, artist_id: int, fx_rate: float = None) -> int:
    """Recompute monthly EUR revenue from USD sales detail for one artist.

    Manual rows (source != 'import') are left untouched. Returns the count of
    import-sourced months now in monthly_revenue (what the Distributeur shows).
    """
    rate = default_fx_rate() if fx_rate is None else float(fx_rate)
    # Three %s rate placeholders: revenue_eur calc, fx_rate column, notes string.
    db.execute_query(_ROLLUP_SQL, (rate, rate, rate, artist_id))
    rows = db.fetch_query(
        "SELECT COUNT(*) FROM distrokid_monthly_revenue "
        "WHERE artist_id = %s AND source = 'import'",
        (artist_id,),
    )
    return int(rows[0][0]) if rows else 0
