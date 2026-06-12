-- 059_distrokid_fx_rate.sql
-- P2 data-integrity: persist the USD->EUR rate used by the DistroKid rollup.
--
-- Before this, distrokid_rollup.py baked the rate (default 0.92) irreversibly into
-- revenue_eur and only echoed it inside the human-readable `notes` string, so the
-- conversion was not queryable nor re-auditable (revenue_eur could not be reversed
-- back to USD). This adds a real column.
--
-- NULL = a manually-entered EUR amount (source != 'import') that was never converted.
-- A value = the rate the import rollup applied; revenue_usd_implied = revenue_eur / fx_rate.
-- Idempotent (ADD COLUMN IF NOT EXISTS).

ALTER TABLE distrokid_monthly_revenue
    ADD COLUMN IF NOT EXISTS fx_rate NUMERIC(8, 5);

COMMENT ON COLUMN distrokid_monthly_revenue.fx_rate IS
    'USD->EUR rate applied by the import rollup. NULL for manual EUR entries. Makes revenue_eur reversible to USD (revenue_eur / fx_rate).';
