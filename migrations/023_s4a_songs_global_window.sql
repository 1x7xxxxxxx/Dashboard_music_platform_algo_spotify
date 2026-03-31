-- Migration 023: add time_window column to s4a_songs_global
-- Allows storing both the 28-day and 12-month Spotify for Artists song snapshots
-- without conflict. time_window values: '28d' | '12m'.
-- Existing rows are assigned the default '12m'.

ALTER TABLE s4a_songs_global
    ADD COLUMN IF NOT EXISTS time_window TEXT NOT NULL DEFAULT '12m';

-- Replace the existing unique constraint to include time_window.
ALTER TABLE s4a_songs_global
    DROP CONSTRAINT IF EXISTS s4a_songs_global_artist_id_song_key;

ALTER TABLE s4a_songs_global
    ADD CONSTRAINT s4a_songs_global_artist_song_window_key
    UNIQUE (artist_id, song, time_window);
