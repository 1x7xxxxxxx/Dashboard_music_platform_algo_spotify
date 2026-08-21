-- Migration 024: redesign s4a_song_playlist_adds
-- Replace (period_start, period_end) key with recorded_at DATE.
-- Rationale: rolling periods (28d, 90d) shift daily, making period-bound keys
-- unreliable — the same entry would never be found the next day.
-- Storing by recorded_at (the date the user entered the value from the S4A UI)
-- creates a time series of snapshots instead.
--
-- ⚠️ SUPERSEDED BY 044 — and made a no-op once 044 has run. Read this before
-- editing. Measured 2026-08-21:
--
-- 044 moved the primary key to (artist_id, song, time_window, recorded_at) so a
-- song can hold one row per window. 024's three-column key became IMPOSSIBLE from
-- that moment: the same song legitimately carries several windows on one
-- recorded_at, so `ADD PRIMARY KEY (artist_id, song, recorded_at)` fails on
-- duplicates — every single time it runs.
--
-- That failure was harmless only as long as the whole set was replayed in order,
-- because 044 came afterwards and put the right key back. The moment 024 is
-- replayed ALONE — which is exactly what a migration ledger does, since a file
-- that never succeeds is never recorded — its unguarded DROP CONSTRAINT on line
-- one DESTROYS 044's key and its ADD fails. The table is then left with NO
-- primary key at all. Observed live on 2026-08-21 while introducing the ledger.
--
-- So the guard below is not cosmetic idempotence: without it this file actively
-- damages a correct schema.

DO $$
BEGIN
    -- `time_window` is 044's marker. If it exists, 044 owns the key: do nothing.
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 's4a_song_playlist_adds' AND column_name = 'time_window'
    ) THEN
        RAISE NOTICE '024 skipped: superseded by 044 (time_window present).';
        RETURN;
    END IF;

    ALTER TABLE s4a_song_playlist_adds
        DROP CONSTRAINT IF EXISTS s4a_song_playlist_adds_pkey;

    ALTER TABLE s4a_song_playlist_adds
        DROP COLUMN IF EXISTS period_start,
        DROP COLUMN IF EXISTS period_end;

    ALTER TABLE s4a_song_playlist_adds
        ADD COLUMN IF NOT EXISTS recorded_at DATE NOT NULL DEFAULT CURRENT_DATE;

    ALTER TABLE s4a_song_playlist_adds
        ADD CONSTRAINT s4a_song_playlist_adds_pkey
        PRIMARY KEY (artist_id, song, recorded_at);
END $$;

CREATE INDEX IF NOT EXISTS idx_s4a_playlist_adds_artist_song
    ON s4a_song_playlist_adds (artist_id, song, recorded_at DESC);
