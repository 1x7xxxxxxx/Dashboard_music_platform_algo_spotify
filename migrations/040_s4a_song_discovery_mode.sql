-- 040_s4a_song_discovery_mode.sql
-- Phase-2 win: un-impute the model feature `IsThisSongOptedIntoSpotifyDiscoveryMode`.
-- The Discovery-Mode opt-in is artist-controlled and visible only in the Spotify for
-- Artists UI (no API), so — like s4a_song_playlist_adds — it is captured via a manual
-- per-song entry in trigger_algo and read by ml_inference.build_features (default 0.0
-- when no entry exists). Mirrors the s4a_song_playlist_adds shape (per-song dated
-- snapshots; latest recorded_at wins). Idempotent.

CREATE TABLE IF NOT EXISTS s4a_song_discovery_mode (
    artist_id    INTEGER NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
    song         TEXT    NOT NULL,
    opted_in     BOOLEAN NOT NULL DEFAULT FALSE,
    collected_at TIMESTAMPTZ DEFAULT now(),
    recorded_at  DATE    NOT NULL DEFAULT CURRENT_DATE,
    PRIMARY KEY (artist_id, song, recorded_at)
);

CREATE INDEX IF NOT EXISTS idx_s4a_discovery_mode_artist_song
    ON s4a_song_discovery_mode (artist_id, song);
