-- 144 — R289 (owner review of the KPI dossier, 2026-09-28): two pages still read bronze.
--
-- 1. SoundCloud (fiche 8) read `MIN(collected_at)` from soundcloud_tracks_daily to sort its
--    titles « latest release first ». The per-title gold view gains that one attribute —
--    appended LAST: `CREATE OR REPLACE VIEW` may add columns at the end, never reorder them,
--    so every existing reader keeps its columns (additive).
-- 2. YouTube (fiche 13) joined youtube_videos + youtube_video_stats by hand. The latest
--    reading of each video becomes a gold view, partitioned by (artist_id, video_id) like
--    every other « latest » view (107) — a video_id alone is not proven unique per tenant.

CREATE OR REPLACE VIEW v_soundcloud_track_latest AS
    SELECT DISTINCT ON (artist_id, track_id)
           artist_id,
           track_id,
           title,
           permalink_url,
           COALESCE(playback_count, 0)::bigint AS playback_count,
           COALESCE(likes_count, 0)::bigint    AS likes_count,
           COALESCE(reposts_count, 0)::bigint  AS reposts_count,
           COALESCE(comment_count, 0)::bigint  AS comment_count,
           collected_at,
           track_created_at,
           -- The first day this title was collected: « latest release first » needs it.
           MIN(collected_at) OVER (PARTITION BY artist_id, track_id) AS first_seen
      FROM soundcloud_tracks_daily
     WHERE artist_id IS NOT NULL
     ORDER BY artist_id, track_id, collected_at DESC;

CREATE OR REPLACE VIEW v_youtube_video_latest AS
    SELECT DISTINCT ON (s.artist_id, s.video_id)
           s.artist_id,
           s.video_id,
           v.title,
           v.published_at,
           v.duration,
           v.thumbnail_url,
           COALESCE(s.view_count, 0)::bigint    AS view_count,
           COALESCE(s.like_count, 0)::bigint    AS like_count,
           COALESCE(s.comment_count, 0)::bigint AS comment_count,
           s.collected_at
      FROM youtube_video_stats s
      JOIN youtube_videos v ON v.video_id = s.video_id AND v.artist_id = s.artist_id
     WHERE s.artist_id IS NOT NULL
     ORDER BY s.artist_id, s.video_id, s.collected_at DESC, v.collected_at DESC;

COMMENT ON VIEW v_youtube_video_latest IS
    'Couche OR (R289) : le dernier relevé de chaque vidéo YouTube, par locataire, avec '
    'ses attributs (titre, publication). YouTube est un COMPTEUR : toute somme par vidéo '
    'se fait sur cette vue, jamais sur youtube_video_stats.';
