-- 061_algo_outcomes_windowed.sql
-- Make s4a_song_algo_outcomes window-aware (7d / 28d / custom), so the artist can track
-- HOW MANY streams each algorithmic playlist (DW/RR/Radio) actually generates once a song
-- has been picked up — over multiple horizons, not only the 28-day ML window.
--
-- The columns become window-agnostic (dw_streams, not dw_streams_28d) and a `time_window`
-- discriminator + optional custom period are added, mirroring s4a_song_playlist_adds.
-- The ML outcome-labelling loop keeps reading ONLY time_window='28d' (the model's target
-- horizon) — the 7d/custom rows are tracking/analytics, never training labels.
-- Idempotent. The table is freshly created (migration 060) and empty, so this is safe.

-- 1. Rename the 28d-suffixed columns to window-agnostic names (guarded: only if old names exist).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 's4a_song_algo_outcomes' AND column_name = 'dw_streams_28d') THEN
        ALTER TABLE s4a_song_algo_outcomes RENAME COLUMN dw_streams_28d TO dw_streams;
        ALTER TABLE s4a_song_algo_outcomes RENAME COLUMN rr_streams_28d TO rr_streams;
        ALTER TABLE s4a_song_algo_outcomes RENAME COLUMN radio_streams_28d TO radio_streams;
    END IF;
END $$;

-- 2. Window discriminator + optional custom range.
ALTER TABLE s4a_song_algo_outcomes ADD COLUMN IF NOT EXISTS time_window TEXT NOT NULL DEFAULT '28d';
ALTER TABLE s4a_song_algo_outcomes ADD COLUMN IF NOT EXISTS period_start DATE;
ALTER TABLE s4a_song_algo_outcomes ADD COLUMN IF NOT EXISTS period_end DATE;

-- 3. Repoint the primary key to include time_window (one snapshot per song/window/day).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 's4a_song_algo_outcomes_pkey') THEN
        ALTER TABLE s4a_song_algo_outcomes DROP CONSTRAINT s4a_song_algo_outcomes_pkey;
    END IF;
    ALTER TABLE s4a_song_algo_outcomes
        ADD CONSTRAINT s4a_song_algo_outcomes_pkey
        PRIMARY KEY (artist_id, song, time_window, recorded_at);
END $$;
