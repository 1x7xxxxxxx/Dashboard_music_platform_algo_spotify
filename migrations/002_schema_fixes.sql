-- Migration 002: Schema fixes for P1/P2/P4 bugs
-- Apply against: spotify_etl database
-- Date: 2026-03-23

\c spotify_etl

-- ============================================================
-- P1: meta_campaigns — add 7 missing columns
-- ============================================================

ALTER TABLE meta_campaigns
    ADD COLUMN IF NOT EXISTS status VARCHAR(50),
    ADD COLUMN IF NOT EXISTS objective VARCHAR(100),
    ADD COLUMN IF NOT EXISTS daily_budget DECIMAL(10, 2),
    ADD COLUMN IF NOT EXISTS lifetime_budget DECIMAL(10, 2),
    ADD COLUMN IF NOT EXISTS end_time TIMESTAMP,
    ADD COLUMN IF NOT EXISTS created_time TIMESTAMP,
    ADD COLUMN IF NOT EXISTS updated_time TIMESTAMP;

-- ============================================================
-- P2: meta_insights — fix UNIQUE constraint to include artist_id
-- ============================================================

ALTER TABLE meta_insights
    DROP CONSTRAINT IF EXISTS meta_insights_ad_id_date_key;

ALTER TABLE meta_insights
    ADD CONSTRAINT meta_insights_artist_ad_date UNIQUE (artist_id, ad_id, date);

-- ============================================================
-- P2: apple_songs_history — add artist_id, backfill, add constraint
-- ============================================================

-- Create table if it doesn't exist yet (e.g. fresh deploy)
CREATE TABLE IF NOT EXISTS apple_songs_history (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    song_name VARCHAR(255) NOT NULL,
    plays INTEGER DEFAULT 0,
    shazam_count INTEGER DEFAULT 0,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add column if table existed without artist_id
ALTER TABLE apple_songs_history
    ADD COLUMN IF NOT EXISTS artist_id INTEGER REFERENCES saas_artists(id);

-- Backfill existing rows to artist 1
UPDATE apple_songs_history SET artist_id = 1 WHERE artist_id IS NULL;

-- Enforce NOT NULL now that backfill is done
ALTER TABLE apple_songs_history
    ALTER COLUMN artist_id SET NOT NULL;

-- Add index
CREATE INDEX IF NOT EXISTS idx_apple_history_artist ON apple_songs_history(artist_id);
CREATE INDEX IF NOT EXISTS idx_apple_history_date ON apple_songs_history(date DESC);

-- ============================================================
-- P2: s4a_song_timeline — backfill null artist_id rows
-- ============================================================

UPDATE s4a_song_timeline SET artist_id = 1 WHERE artist_id IS NULL;

-- ============================================================
-- P4: Remove stale SQL views (replaced by DISTINCT ON in Python)
-- ============================================================

DROP VIEW IF EXISTS view_soundcloud_latest;
DROP VIEW IF EXISTS view_instagram_latest;
