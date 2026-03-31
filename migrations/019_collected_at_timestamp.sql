-- Migration 019: Fix collected_at columns from DATE to TIMESTAMP WITHOUT TIME ZONE
-- Affected tables: soundcloud_tracks_daily, instagram_daily_stats
-- Root cause: collectors wrote datetime.now().strftime('%Y-%m-%d') → DATE column
--             freshness query converted DATE to midnight → always showed ~Xh ago
--
-- Type: TIMESTAMP WITHOUT TIME ZONE — consistent with all other tables in schema.
-- ::date cast is IMMUTABLE on this type (safe for expression indexes).
-- Unique indexes rebuilt on (artist_id, …, (collected_at::date)) to preserve
-- one-row-per-day guarantee regardless of intra-day timestamp.

-- ── soundcloud_tracks_daily ──────────────────────────────────────────────────

ALTER TABLE soundcloud_tracks_daily
    ALTER COLUMN collected_at TYPE TIMESTAMP WITHOUT TIME ZONE
    USING collected_at::timestamp without time zone;

ALTER TABLE soundcloud_tracks_daily
    DROP CONSTRAINT soundcloud_tracks_daily_artist_id_track_id_collected_at_key;

DROP INDEX IF EXISTS idx_sc_tracks_date;

CREATE UNIQUE INDEX soundcloud_tracks_daily_artist_id_track_id_day_key
    ON soundcloud_tracks_daily (artist_id, track_id, (collected_at::date));

CREATE INDEX idx_sc_tracks_date
    ON soundcloud_tracks_daily (collected_at);

-- ── instagram_daily_stats ────────────────────────────────────────────────────

ALTER TABLE instagram_daily_stats
    ALTER COLUMN collected_at TYPE TIMESTAMP WITHOUT TIME ZONE
    USING collected_at::timestamp without time zone;

ALTER TABLE instagram_daily_stats
    DROP CONSTRAINT instagram_daily_stats_artist_id_ig_user_id_collected_at_key;

DROP INDEX IF EXISTS idx_insta_date;

CREATE UNIQUE INDEX instagram_daily_stats_artist_id_ig_user_id_day_key
    ON instagram_daily_stats (artist_id, ig_user_id, (collected_at::date));

CREATE INDEX idx_insta_date
    ON instagram_daily_stats (collected_at);
