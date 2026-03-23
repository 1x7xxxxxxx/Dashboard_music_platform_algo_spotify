-- Migration 003 — YouTube UNIQUE constraints
-- Prevents duplicate history rows on re-run.
-- Safe to run multiple times (IF NOT EXISTS on constraints).
-- Apply: psql -h localhost -p 5433 -U postgres -d spotify_etl -f migrations/003_youtube_unique.sql

-- youtube_channel_history: one snapshot per artist/channel/day
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'uq_yt_channel_history_artist_channel_date'
    ) THEN
        -- Remove exact duplicates first (keep lowest id)
        DELETE FROM youtube_channel_history a
        USING youtube_channel_history b
        WHERE a.id > b.id
          AND a.artist_id = b.artist_id
          AND a.channel_id = b.channel_id
          AND a.collected_at::date = b.collected_at::date;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_yt_channel_history_artist_channel_date
    ON youtube_channel_history (artist_id, channel_id, (collected_at::date));

-- youtube_video_stats: one snapshot per artist/video/day
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'uq_yt_video_stats_artist_video_date'
    ) THEN
        DELETE FROM youtube_video_stats a
        USING youtube_video_stats b
        WHERE a.id > b.id
          AND a.artist_id = b.artist_id
          AND a.video_id = b.video_id
          AND a.collected_at::date = b.collected_at::date;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_yt_video_stats_artist_video_date
    ON youtube_video_stats (artist_id, video_id, (collected_at::date));
