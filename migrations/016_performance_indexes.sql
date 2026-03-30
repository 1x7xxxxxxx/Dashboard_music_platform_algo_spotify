-- Migration 016: Performance indexes
-- Adds composite indexes on (artist_id, date) for the 4 most-queried tables.
-- Eliminates full-table scans on artist_id for multi-tenant aggregate queries.

-- s4a_song_timeline — largest table, every stream aggregate scans artist_id
CREATE INDEX IF NOT EXISTS idx_s4a_timeline_artist_date
    ON s4a_song_timeline(artist_id, date DESC);

-- soundcloud_tracks_daily — DISTINCT ON (track_id) requires composite sort
CREATE INDEX IF NOT EXISTS idx_soundcloud_tracks_artist_track_date
    ON soundcloud_tracks_daily(artist_id, track_id, collected_at DESC);

-- meta_insights_performance_day — ROI + freshness queries filter on both cols
CREATE INDEX IF NOT EXISTS idx_mip_day_artist_date
    ON meta_insights_performance_day(artist_id, day_date DESC);

-- track_popularity_history — popularity KPI: WHERE artist_id ORDER BY date DESC LIMIT 1
CREATE INDEX IF NOT EXISTS idx_track_pop_history_artist_date
    ON track_popularity_history(artist_id, date DESC);
