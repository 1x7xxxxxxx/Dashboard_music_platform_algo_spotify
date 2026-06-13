-- 063_drop_orphan_schema_drift.sql
-- Remove prod-extra ORPHANS surfaced by `make schema-check` (2026-06-13) so prod ==
-- canonical. Done via a migration (never a manual ALTER on prod — that is the very
-- drift this guards against). Idempotent: on a fresh canonical the DROPs are no-ops
-- (these don't exist there) and the id ADDs are no-ops (canonical already has id);
-- on prod they drop the orphans + add the SERIAL id the older tables lacked.
-- Safety: all dropped columns held 0 non-null values; meta_spotify_mapping had 0 rows
-- (dead, superseded by campaign_track_mapping); the youtube_videos counts are
-- duplicated in youtube_video_stats (current code reads them there).

DROP TABLE IF EXISTS meta_spotify_mapping;

ALTER TABLE meta_ads         DROP COLUMN IF EXISTS video_file_name;
ALTER TABLE meta_adsets      DROP COLUMN IF EXISTS targeting_optimization;
ALTER TABLE youtube_channels DROP COLUMN IF EXISTS title;
ALTER TABLE youtube_videos   DROP COLUMN IF EXISTS view_count;
ALTER TABLE youtube_videos   DROP COLUMN IF EXISTS like_count;
ALTER TABLE youtube_videos   DROP COLUMN IF EXISTS comment_count;

-- Align the older prod youtube tables to the canonical SERIAL id (column-level parity;
-- prod keeps video_id/channel_id as its PK — a benign constraint-only difference).
ALTER TABLE youtube_channels ADD COLUMN IF NOT EXISTS id SERIAL;
ALTER TABLE youtube_videos   ADD COLUMN IF NOT EXISTS id SERIAL;
