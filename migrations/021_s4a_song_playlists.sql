-- Migration 021: create s4a_song_playlists
-- Stores playlist placements for each song as entered manually from the
-- Spotify for Artists UI (data not available in CSV exports).

CREATE TABLE IF NOT EXISTS s4a_song_playlists (
    id           SERIAL PRIMARY KEY,
    artist_id    INTEGER NOT NULL,
    song         TEXT NOT NULL,
    title        TEXT NOT NULL,
    author       TEXT NOT NULL DEFAULT '-',
    listeners    INTEGER DEFAULT 0,
    streams      INTEGER DEFAULT 0,
    date_added   DATE,
    collected_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (artist_id, song, title)
);

CREATE INDEX IF NOT EXISTS idx_s4a_playlists_artist_song
    ON s4a_song_playlists (artist_id, song);
