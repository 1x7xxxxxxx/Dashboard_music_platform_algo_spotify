-- Migration 051 — DistroKid sales detail (B2 phase 2: TSV/CSV import)
-- Run: make migrate   (or, from PowerShell, see CLAUDE.md § Running Migrations)
--
-- Raw lines from the DistroKid "bank details" export: one row per
-- store × track × country × sale-month, amounts in USD (NUMERIC(14,10) —
-- per-stream earnings carry up to 10 decimals). Rolled up into
-- distrokid_monthly_revenue (EUR) by src/utils/distrokid_rollup.py with an
-- explicit USD→EUR rate. Format: .claude/dev-docs/distrokid-export-format.md.

CREATE TABLE IF NOT EXISTS distrokid_sales_detail (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    sale_year INTEGER NOT NULL,
    sale_month INTEGER NOT NULL CHECK (sale_month BETWEEN 1 AND 12),
    reporting_date DATE NOT NULL,
    store TEXT NOT NULL DEFAULT '',
    artist_name TEXT,
    title TEXT NOT NULL DEFAULT '',
    isrc TEXT NOT NULL DEFAULT '',
    upc TEXT,
    quantity INTEGER NOT NULL DEFAULT 0,
    team_percentage NUMERIC(6, 2),
    source_type TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    songwriter_royalties_usd NUMERIC(14, 10) DEFAULT 0,
    earnings_usd NUMERIC(14, 10) NOT NULL DEFAULT 0,
    recoup_usd NUMERIC(14, 10) DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_distrokid_sale UNIQUE
        (artist_id, isrc, title, sale_year, sale_month,
         reporting_date, store, country, source_type)
);

CREATE INDEX IF NOT EXISTS idx_distrokid_sales_artist
    ON distrokid_sales_detail(artist_id);

CREATE INDEX IF NOT EXISTS idx_distrokid_sales_period
    ON distrokid_sales_detail(artist_id, sale_year DESC, sale_month DESC);

CREATE INDEX IF NOT EXISTS idx_distrokid_sales_isrc
    ON distrokid_sales_detail(isrc);

COMMENT ON TABLE distrokid_sales_detail IS
    'Raw DistroKid bank-details lines (USD). Monthly EUR rollup → distrokid_monthly_revenue.';
