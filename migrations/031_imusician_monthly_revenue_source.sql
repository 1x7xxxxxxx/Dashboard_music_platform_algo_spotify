-- 031 — Add `source` to imusician_monthly_revenue.
-- The CSV import now rolls up imusician_sales_detail into monthly totals so the
-- Distributeur view + ROI helpers (which read monthly_revenue) surface imported
-- data. `source` distinguishes auto-imported rows from manual entries so the
-- roll-up never clobbers a hand-typed value (ON CONFLICT ... WHERE source='import').
ALTER TABLE imusician_monthly_revenue
    ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'manual';
