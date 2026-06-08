-- ============================================================
-- 042 — apple_songs_history: enforce one snapshot per (artist, song, day)
-- ============================================================
-- Why: the Apple DAG historises a daily snapshot via a per-row DELETE then a
-- batch INSERT. Under autocommit (PostgresHandler), a crash between DELETE and
-- INSERT loses the row, and a re-run can duplicate it — there is no UNIQUE
-- constraint to guard against it. Adding one lets the DAG switch to an atomic
-- ON CONFLICT upsert (idempotent, race-free).
--
-- Idempotent: dedup first (keep the latest id per key), then add the constraint
-- only if absent.

-- 1. Collapse existing duplicates, keeping the most recent row per key.
DELETE FROM apple_songs_history a
USING apple_songs_history b
WHERE a.artist_id = b.artist_id
  AND a.song_name = b.song_name
  AND a.date = b.date
  AND a.id < b.id;

-- 2. Add the UNIQUE constraint only if it does not already exist.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_apple_history_artist_song_date'
    ) THEN
        ALTER TABLE apple_songs_history
            ADD CONSTRAINT uq_apple_history_artist_song_date
            UNIQUE (artist_id, song_name, date);
    END IF;
END $$;
