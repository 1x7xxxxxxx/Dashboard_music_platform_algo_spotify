-- ============================================================
-- 043 — s4a_songs_global / s4a_song_saves_daily: normalise '?' -> '_'
-- ============================================================
-- Why: s4a_songs_global.song comes from the CSV "song" column and keeps '?',
-- but s4a_song_timeline (filename-derived) and ml_song_predictions use '_'.
-- Exact-match joins (Vue Globale Listeners/Saves tiles, the 28d gate, and the
-- ml_inference Saves/listeners/ratio features) therefore silently returned 0
-- for every '?'-titled track. The parser now writes the canonical '_' form;
-- this backfills existing rows so the two representations align.
--
-- Idempotent: only touches rows still containing '?'. No collision risk — each
-- (song, time_window) appears once and its '_' twin does not pre-exist.

UPDATE s4a_songs_global
SET song = REPLACE(song, '?', '_')
WHERE song LIKE '%?%';

-- Same normalisation for the saves time series derived from the snapshot,
-- so the resurrection radar joins on the canonical key too.
UPDATE s4a_song_saves_daily
SET song = REPLACE(song, '?', '_')
WHERE song LIKE '%?%';
