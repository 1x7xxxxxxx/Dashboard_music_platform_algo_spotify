-- Migration 020: add playlist_adds and saves to s4a_audience
-- These columns exist in the Spotify for Artists audience-timeline CSV export
-- but were not captured in the original schema.

ALTER TABLE s4a_audience
    ADD COLUMN IF NOT EXISTS playlist_adds INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS saves         INTEGER DEFAULT 0;
