-- 038 — Daily saves history for the long-tail "resurrection" radar.
-- s4a_songs_global only carries a rolling 28-day saves snapshot (no time series),
-- so a sudden save spike on an old song can't be detected. This table historises
-- the per-song saves value once a day (written by the ml_scoring_daily DAG via
-- src/utils/saves_history.snapshot_saves). Detection stays dormant until ~2 weeks
-- of history accumulate. Idempotent: safe to re-run.
CREATE TABLE IF NOT EXISTS s4a_song_saves_daily (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    song VARCHAR(255) NOT NULL,
    snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
    saves INTEGER,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, song, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_saves_daily_artist_song
    ON s4a_song_saves_daily(artist_id, song, snapshot_date DESC);
