-- Migration 034 — Redefine artist_wrapped "top" metric as the artist's own super-fans
-- The previous top_artist_name / top_artist_fan_pct modelled a SIMILAR artist and a
-- shared-fans percentage. The real metric is the artist's own fans who ranked them as a
-- top artist: a count of fans + the rank threshold (e.g. 11 fans had you in their top 5).
-- Idempotent: `make migrate` replays every migrations/*.sql on each run.
-- Run: Get-Content migrations/034_wrapped_top_fans.sql | docker exec -i postgres_spotify_airflow psql -U postgres -d spotify_etl

ALTER TABLE artist_wrapped ADD COLUMN IF NOT EXISTS top_fans_count INTEGER;
ALTER TABLE artist_wrapped ADD COLUMN IF NOT EXISTS top_fans_rank  INTEGER;

ALTER TABLE artist_wrapped DROP COLUMN IF EXISTS top_artist_name;
ALTER TABLE artist_wrapped DROP COLUMN IF EXISTS top_artist_fan_pct;
