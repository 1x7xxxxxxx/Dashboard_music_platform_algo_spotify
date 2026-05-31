-- Migration 033 — Convert artist_wrapped gain columns to percentages
-- The 4 *_gain columns were generic signed integers; they now hold annual
-- growth percentages (e.g. +45.3). Renamed to *_gain_pct and widened to
-- DECIMAL(7,2) to carry one signed decimal percentage with comfortable range.
-- Idempotent: `make migrate` replays every migrations/*.sql on each run.
-- Run: Get-Content migrations/033_wrapped_gains_pct.sql | docker exec -i postgres_spotify_airflow psql -U postgres -d spotify_etl

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'artist_wrapped' AND column_name = 'listener_gain') THEN
        ALTER TABLE artist_wrapped RENAME COLUMN listener_gain TO listener_gain_pct;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'artist_wrapped' AND column_name = 'stream_gain') THEN
        ALTER TABLE artist_wrapped RENAME COLUMN stream_gain TO stream_gain_pct;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'artist_wrapped' AND column_name = 'save_gain') THEN
        ALTER TABLE artist_wrapped RENAME COLUMN save_gain TO save_gain_pct;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'artist_wrapped' AND column_name = 'playlist_add_gain') THEN
        ALTER TABLE artist_wrapped RENAME COLUMN playlist_add_gain TO playlist_add_gain_pct;
    END IF;
END $$;

-- Type widening is idempotent (re-casting to the same type is a no-op).
ALTER TABLE artist_wrapped ALTER COLUMN listener_gain_pct     TYPE DECIMAL(7, 2);
ALTER TABLE artist_wrapped ALTER COLUMN stream_gain_pct       TYPE DECIMAL(7, 2);
ALTER TABLE artist_wrapped ALTER COLUMN save_gain_pct         TYPE DECIMAL(7, 2);
ALTER TABLE artist_wrapped ALTER COLUMN playlist_add_gain_pct TYPE DECIMAL(7, 2);
