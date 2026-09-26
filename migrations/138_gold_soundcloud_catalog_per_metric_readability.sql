-- ═══════════════════════════════════════════════════════════════════════════
-- 138 — SoundCloud catalog: readability PER METRIC, as at the track grain
-- ═══════════════════════════════════════════════════════════════════════════
-- THE DEFECT, MEASURED ON 2026-09-26
-- ----------------------------------
-- Migration 132 gave `v_soundcloud_catalog_daily` ONE verdict, `lisible`, and
-- computed it from PLAYS only. It named the second failure era itself — "likes
-- at 0 alone, 2026-03-30 → 2026-05-14, before the OAuth switch" — but defined
-- `likes_lisibles` only at the TRACK grain. The catalog grain had nothing.
--
--     SELECT day, plays, likes, lisible FROM v_soundcloud_catalog_daily
--      WHERE artist_id = 1 AND day BETWEEN '2026-03-28' AND '2026-05-16';
--     → 2026-03-30, 03-31, 04-01, 04-03, 05-14 : likes = 0, lisible = t
--       2026-05-15                            : likes = 1309
--
-- The catalog engagement panel keeps `df[df.lisible]` and draws likes, reposts
-- and comments from it — so it drew 1 333 → 0 → 1 309, a collapse that never
-- happened. The per-track base-100 chart, which reads the per-metric flags,
-- did not.
--
-- THE RULE — the one of `v_soundcloud_track_daily`, lifted to the catalog
-- -----------------------------------------------------------------------
-- A catalog metric is readable on a day when EVERY track's reading of it is:
-- a lifetime counter at exactly 0 after having been positive ON THE SAME TRACK
-- is a failed read, not a listener's gesture. Taking the AND over tracks, not a
-- rule on the catalog sum, is deliberate: a day where ONE track's likes read 0
-- sums to a smaller, plausible total that no rule on the sum can see.
--
-- Nothing else changes: columns are APPENDED (Postgres permits appending
-- columns on a replaced view), `lisible` keeps its definition, and `v_soundcloud_track_daily`, which
-- joins this view on `lisible`, is untouched. Raw rows stay as they are.

CREATE OR REPLACE VIEW v_soundcloud_catalog_daily AS
    WITH par_jour AS (
        SELECT artist_id, date(collected_at) AS day, track_id,
               (ARRAY_AGG(playback_count ORDER BY collected_at DESC))[1] AS plays,
               (ARRAY_AGG(likes_count    ORDER BY collected_at DESC))[1] AS likes,
               (ARRAY_AGG(reposts_count  ORDER BY collected_at DESC))[1] AS reposts,
               (ARRAY_AGG(comment_count  ORDER BY collected_at DESC))[1] AS comments
          FROM soundcloud_tracks_daily
         GROUP BY artist_id, date(collected_at), track_id
    ), par_titre AS (
        -- Per track: is this zero a failed read? Same predicate as the track view.
        SELECT *,
               NOT (likes = 0 AND MAX(likes) OVER w > 0)       AS likes_ok,
               NOT (reposts = 0 AND MAX(reposts) OVER w > 0)   AS reposts_ok,
               NOT (comments = 0 AND MAX(comments) OVER w > 0) AS comments_ok
          FROM par_jour
        WINDOW w AS (PARTITION BY artist_id, track_id ORDER BY day
                     ROWS UNBOUNDED PRECEDING)
    ), totaux AS (
        SELECT artist_id, day,
               COUNT(*)::int            AS tracks,
               SUM(plays)::bigint       AS plays,
               SUM(likes)::bigint       AS likes,
               SUM(reposts)::bigint     AS reposts,
               SUM(comments)::bigint    AS comments,
               -- COALESCE: a NULL counter is not a failed read of 0; it is
               -- absent, and SUM already skips it.
               BOOL_AND(COALESCE(likes_ok, TRUE))    AS likes_lisibles,
               BOOL_AND(COALESCE(reposts_ok, TRUE))  AS reposts_lisibles,
               BOOL_AND(COALESCE(comments_ok, TRUE)) AS comments_lisibles
          FROM par_titre
         GROUP BY artist_id, day
    )
    SELECT artist_id, day, tracks, plays, likes, reposts, comments,
           (plays >= MAX(plays) OVER (PARTITION BY artist_id ORDER BY day
                                      ROWS UNBOUNDED PRECEDING)) AS lisible,
           likes_lisibles, reposts_lisibles, comments_lisibles
      FROM totaux;

COMMENT ON VIEW v_soundcloud_catalog_daily IS
    'Couche OR (ADR-019) : les quatre compteurs SoundCloud du CATALOGUE, au grain '
    '(locataire, jour). Un jour porte le DERNIER relevé de chaque titre. `lisible` '
    'est FAUX quand le cumul des ÉCOUTES redescend sous son maximum (collecte ratée). '
    'likes/reposts/comments_lisibles (migration 138) sont FAUX quand un titre au '
    'moins lit 0 sur ce compteur après l''avoir lu positif — la règle du grain titre, '
    'relevée au catalogue : les likes à 0 du 2026-03-30 au 2026-05-14 étaient '
    '`lisible` et dessinés.';
