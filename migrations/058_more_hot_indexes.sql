-- Migration 058 — remaining hot indexes found in the 2nd pre-deployment audit pass.
-- Idempotent (IF NOT EXISTS). Companion to 057.

-- Home page (every tenant load): COUNT(*) WHERE artist_id = %s AND status = 'success'
-- (src/dashboard/views/home.py). etl_run_log had indexes leading with dag_id / status /
-- platform — none leads with artist_id → seq scan of an append-only log on the hottest
-- page. (artist_id, status) serves the home onboarding/run check directly.
CREATE INDEX IF NOT EXISTS idx_etl_run_log_artist_status
    ON etl_run_log (artist_id, status);

-- Admin ETL-logs views range/sort on bare started_at with no leading equality predicate
-- (src/dashboard/views/etl_logs.py). The existing (dag_id|status|platform, started_at)
-- indexes can't serve a standalone `ORDER BY started_at DESC LIMIT n`. Admin-only (P3).
CREATE INDEX IF NOT EXISTS idx_etl_run_log_started
    ON etl_run_log (started_at DESC);

-- Instagram view filters by artist_id and sorts by collected_at; only a bare
-- (collected_at) index + a unique (artist_id, ig_user_id, collected_at::date) existed —
-- neither serves `WHERE artist_id = %s ORDER BY collected_at DESC` well.
CREATE INDEX IF NOT EXISTS idx_insta_artist_collected
    ON instagram_daily_stats (artist_id, collected_at DESC);

-- NOTE: apple_songs_history (artist_id, song_name) was NOT added — the existing UNIQUE
-- (artist_id, song_name, date) already covers the `WHERE artist_id AND song_name IN (...)`
-- prefix, so a separate index would be redundant.
