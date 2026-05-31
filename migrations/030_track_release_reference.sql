-- Migration 030: track_release_reference — canonical per-track release date.
-- Spotify for Artists (s4a_songs_global.release_date) is the authoritative source
-- of real release dates. Other platforms (Apple Music, SoundCloud, …) key tracks
-- by a free-text name that differs in spelling (accents, "(Remix)" vs " - Remix",
-- " - Original"). This dimension table holds one row per canonical track, keyed by
-- a normalized match_key (see src/utils/track_matching.normalize_track_title), so
-- any name-keyed view can join to it and obtain the true release_date.
--
-- Rebuilt from s4a_songs_global on every S4A CSV import (see upload_csv.py).

CREATE TABLE IF NOT EXISTS track_release_reference (
    id           SERIAL       PRIMARY KEY,
    artist_id    INTEGER      NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
    match_key    VARCHAR(255) NOT NULL,
    title        VARCHAR(255) NOT NULL,
    release_date DATE,
    source       VARCHAR(40)  NOT NULL DEFAULT 's4a_songs_global',
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (artist_id, match_key)
);

CREATE INDEX IF NOT EXISTS idx_track_release_ref_artist
    ON track_release_reference (artist_id);
