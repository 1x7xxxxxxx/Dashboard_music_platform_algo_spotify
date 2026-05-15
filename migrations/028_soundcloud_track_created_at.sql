-- Migration 028: SoundCloud true release date
-- Adds soundcloud_tracks_daily.track_created_at (SC API track.created_at — the
-- real upload timestamp). entity_period_filter previously ordered "latest
-- release" by MIN(collected_at) (= first ingest, NOT release) → wrong default
-- track. Idempotent. Nullable: legacy rows + tracks the API omits it for.
-- No UNIQUE/upsert impact (collector uses insert_many + same-day DELETE; the
-- day-uniqueness index from migration 019 is unaffected). The first
-- soundcloud_daily run after deploy backfills today's rows (full re-fetch).

ALTER TABLE soundcloud_tracks_daily
    ADD COLUMN IF NOT EXISTS track_created_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_sc_tracks_created_at
    ON soundcloud_tracks_daily (artist_id, track_created_at DESC);
