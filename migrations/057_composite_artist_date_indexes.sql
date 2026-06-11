-- Migration 057 — composite (artist_id, date) indexes for the heaviest range scans.
--
-- Pre-deployment performance pass. The schema already indexes single artist_id and
-- single date columns separately, but the hot dashboard queries filter
-- `artist_id = %s AND <date> BETWEEN …` (or GROUP BY year, month under an artist
-- filter). Postgres can only use one single-column index then recheck the rest in
-- memory — a bitmap-heap recheck that becomes costly on a small, disk-bound VPS as
-- tenant/row counts grow. These composites turn the hot paths into pure index scans.
--
-- Idempotent (IF NOT EXISTS). Safe to re-run via `make migrate`.
--
-- NOTE: sacem_statement already has (artist_id, line_date) from migration 055, and
-- meta_insights_performance_day already has (artist_id, day_date) from migration 016 —
-- so those hot paths are already covered and are intentionally omitted here.

-- Meta lifetime insights (campaign-level), queried by artist + date_start range
-- (meta_x_spotify, meta_ads_overview). Only single-column indexes existed.
CREATE INDEX IF NOT EXISTS idx_mip_artist_datestart
    ON meta_insights_performance (artist_id, date_start DESC);

CREATE INDEX IF NOT EXISTS idx_mie_artist_datestart
    ON meta_insights_engagement (artist_id, date_start DESC);

-- Monthly revenue tables: the existing (year DESC, month DESC) index is GLOBAL (not
-- per-tenant) and unusable under an artist_id filter; the revenue VIEW groups
-- `WHERE artist_id = %s … GROUP BY year, month`. Per-tenant composite needed.
CREATE INDEX IF NOT EXISTS idx_imusician_revenue_artist_period
    ON imusician_monthly_revenue (artist_id, year, month);

CREATE INDEX IF NOT EXISTS idx_distrokid_revenue_artist_period
    ON distrokid_monthly_revenue (artist_id, year, month);

-- S4A audience: artist_id and date were indexed separately (and init_db.sql lacked the
-- artist_id index entirely — schema drift vs create_missing_tables.sql). One composite
-- covers the artist+date-sorted reads and removes the drift gap.
CREATE INDEX IF NOT EXISTS idx_s4a_audience_artist_date
    ON s4a_audience (artist_id, date DESC);
