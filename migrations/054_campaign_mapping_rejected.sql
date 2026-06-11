-- 054_campaign_mapping_rejected.sql
-- Tombstone for Meta-campaign suggestions the user rejected (so they stop being
-- re-suggested). Kept SEPARATE from campaign_track_mapping on purpose: every consumer
-- of that table (meta_x_spotify, ROI Breakeven, CPR optimizer, PDF) reads it WITHOUT a
-- status filter, so a 'rejected' row there would silently corrupt attribution. A
-- dedicated table leaves those queries untouched. Idempotent.

CREATE TABLE IF NOT EXISTS campaign_mapping_rejected (
    artist_id     INTEGER NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
    campaign_name TEXT    NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (artist_id, campaign_name)
);
