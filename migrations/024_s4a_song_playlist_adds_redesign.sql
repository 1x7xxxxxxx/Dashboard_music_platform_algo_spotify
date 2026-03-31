-- Migration 024: redesign s4a_song_playlist_adds
-- Replace (period_start, period_end) key with recorded_at DATE.
-- Rationale: rolling periods (28d, 90d) shift daily, making period-bound keys
-- unreliable — the same entry would never be found the next day.
-- Storing by recorded_at (the date the user entered the value from the S4A UI)
-- creates a time series of snapshots instead.

ALTER TABLE s4a_song_playlist_adds
    DROP CONSTRAINT s4a_song_playlist_adds_pkey;

ALTER TABLE s4a_song_playlist_adds
    DROP COLUMN IF EXISTS period_start,
    DROP COLUMN IF EXISTS period_end;

ALTER TABLE s4a_song_playlist_adds
    ADD COLUMN IF NOT EXISTS recorded_at DATE NOT NULL DEFAULT CURRENT_DATE;

ALTER TABLE s4a_song_playlist_adds
    ADD PRIMARY KEY (artist_id, song, recorded_at);

CREATE INDEX IF NOT EXISTS idx_s4a_playlist_adds_artist_song
    ON s4a_song_playlist_adds (artist_id, song, recorded_at DESC);
