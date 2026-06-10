-- 052_s4a_nonalgo_radio_manual.sql
-- Phase-2 win: un-impute the two last model features that were hard-coded to 0
-- in ml_inference.build_features (no live source):
--   * NonAlgoStreams28Days_log               (per-song, 28-day organic/non-algo streams)
--   * HowManySongsDoYouHaveInRadioRightNow   (per-artist, # of songs currently in Radio)
-- Both are visible only in the Spotify for Artists UI (no API), so — exactly like
-- s4a_song_playlist_adds / s4a_song_discovery_mode — they are captured via manual
-- entry in the Saisie S4A view and read by ml_inference (default 0 when no entry
-- exists, preserving behaviour for tenants who don't fill them in). Dated snapshots,
-- latest recorded_at wins. Idempotent.

-- Per-song, 28-day non-algorithmic streams (search, profile, direct — not DW/RR/Radio/autoplay).
CREATE TABLE IF NOT EXISTS s4a_song_nonalgo_streams (
    artist_id    INTEGER NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
    song         TEXT    NOT NULL,
    streams_28d  INTEGER NOT NULL DEFAULT 0,
    collected_at TIMESTAMPTZ DEFAULT now(),
    recorded_at  DATE    NOT NULL DEFAULT CURRENT_DATE,
    PRIMARY KEY (artist_id, song, recorded_at)
);

CREATE INDEX IF NOT EXISTS idx_s4a_nonalgo_streams_artist_song
    ON s4a_song_nonalgo_streams (artist_id, song);

-- Per-artist count of songs currently pushed in Spotify Radio.
CREATE TABLE IF NOT EXISTS s4a_artist_radio_count (
    artist_id    INTEGER NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
    song_count   INTEGER NOT NULL DEFAULT 0,
    collected_at TIMESTAMPTZ DEFAULT now(),
    recorded_at  DATE    NOT NULL DEFAULT CURRENT_DATE,
    PRIMARY KEY (artist_id, recorded_at)
);
