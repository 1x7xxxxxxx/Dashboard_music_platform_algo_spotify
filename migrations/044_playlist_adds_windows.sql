-- ============================================================
-- 044 — s4a_song_playlist_adds: windowed snapshots (7d / 28d / 12m / custom)
-- ============================================================
-- Why: S4A reports playlist adds per song over selectable windows (7 days,
-- 28 days, 12 months) plus arbitrary custom ranges (key in the first days after
-- a release). The table previously held a single cumulative count per date and
-- the ML summed the last 28 days — wrong for manual windowed entry. We add a
-- time_window dimension (+ period_start/period_end for custom ranges) so each
-- window is stored as its own snapshot, and the ML reads the 28d snapshot.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS + guarded PK swap. Existing rows (none in
-- practice) default to time_window='28d', preserving prior uniqueness.

ALTER TABLE s4a_song_playlist_adds
    ADD COLUMN IF NOT EXISTS time_window  TEXT NOT NULL DEFAULT '28d';
ALTER TABLE s4a_song_playlist_adds
    ADD COLUMN IF NOT EXISTS period_start DATE;
ALTER TABLE s4a_song_playlist_adds
    ADD COLUMN IF NOT EXISTS period_end   DATE;

-- Move the primary key to include time_window so the same song can hold one row
-- per window on a given recorded_at.
ALTER TABLE s4a_song_playlist_adds DROP CONSTRAINT IF EXISTS s4a_song_playlist_adds_pkey;
ALTER TABLE s4a_song_playlist_adds
    ADD CONSTRAINT s4a_song_playlist_adds_pkey
    PRIMARY KEY (artist_id, song, time_window, recorded_at);

CREATE INDEX IF NOT EXISTS idx_s4a_playlist_adds_window
    ON s4a_song_playlist_adds (artist_id, song, time_window, recorded_at DESC);
