"""Roll up imusician_sales_detail into imusician_monthly_revenue.

Type: Utility
Uses: PostgresHandler.execute_query
Triggers: called by the CSV import (upload_csv) after an imusician_sales import
Persists in: imusician_monthly_revenue (source='import' rows only)
Depends on: imusician_sales_detail, imusician_monthly_revenue

The Distributeur view and the ROI helpers read imusician_monthly_revenue, but the
CSV import writes per-line detail to imusician_sales_detail. This bridges the two:
sum the detail per (year, month) and upsert into monthly_revenue, tagging the rows
source='import'. The ON CONFLICT WHERE clause preserves any manual entry for the
same month — a hand-typed value is never overwritten by the roll-up.
"""

_ROLLUP_SQL = """
    INSERT INTO imusician_monthly_revenue
        (artist_id, year, month, revenue_eur, source, notes, updated_at)
    SELECT artist_id, sales_year, sales_month,
           ROUND(SUM(revenue_eur)::numeric, 2),
           'import',
           'Agrégé automatiquement depuis l''import iMusician',
           CURRENT_TIMESTAMP
    FROM imusician_sales_detail
    WHERE artist_id = %s
    GROUP BY artist_id, sales_year, sales_month
    ON CONFLICT (artist_id, year, month) DO UPDATE
        SET revenue_eur = EXCLUDED.revenue_eur,
            source = 'import',
            updated_at = CURRENT_TIMESTAMP
        WHERE imusician_monthly_revenue.source = 'import'
"""


def rollup_sales_to_monthly(db, artist_id: int) -> int:
    """Recompute monthly revenue from sales_detail for one artist. Returns import months.

    Manual rows (source != 'import') are left untouched. The return value is the count
    of import-sourced months now in monthly_revenue (what the Distributeur view shows).
    """
    db.execute_query(_ROLLUP_SQL, (artist_id,))
    rows = db.fetch_query(
        "SELECT COUNT(*) FROM imusician_monthly_revenue "
        "WHERE artist_id = %s AND source = 'import'",
        (artist_id,),
    )
    return int(rows[0][0]) if rows else 0
