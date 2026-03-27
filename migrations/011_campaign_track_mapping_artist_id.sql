-- Migration 011: add artist_id to campaign_track_mapping for multi-tenant isolation
-- Idempotent — safe to re-run.

ALTER TABLE campaign_track_mapping
    ADD COLUMN IF NOT EXISTS artist_id INTEGER REFERENCES saas_artists(id) ON DELETE CASCADE;

-- Backfill existing rows: assign to artist_id = 1 (first artist, adjust if needed)
UPDATE campaign_track_mapping SET artist_id = 1 WHERE artist_id IS NULL;

-- Enforce NOT NULL once backfill is done
ALTER TABLE campaign_track_mapping ALTER COLUMN artist_id SET NOT NULL;

-- Drop old unique constraint and replace with per-artist one
ALTER TABLE campaign_track_mapping
    DROP CONSTRAINT IF EXISTS campaign_track_mapping_campaign_name_track_name_key;

ALTER TABLE campaign_track_mapping
    ADD CONSTRAINT campaign_track_mapping_artist_campaign_track_key
    UNIQUE (artist_id, campaign_name, track_name);

-- Index for fast per-artist lookups
CREATE INDEX IF NOT EXISTS idx_ctm_artist_id ON campaign_track_mapping(artist_id);
