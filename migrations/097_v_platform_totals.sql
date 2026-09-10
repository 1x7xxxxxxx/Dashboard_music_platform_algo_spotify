-- 097 — La couche OR : une définition par métrique, et une seule.
--
-- ADR-019. Le désaccord mesuré le 2026-09-10 : le total de vues YouTube avait TROIS
-- définitions incompatibles dans le dépôt.
--
--   1. `platform_timeseries._SQL_LIFETIME_YOUTUBE`  → somme des compteurs PAR VIDÉO
--      (le dernier relevé de chacune). La bonne.
--   2. `kpi_helpers.get_total_views_youtube`        → `youtube_channel_history.view_count`,
--      le compteur de CHAÎNE, prouvé ~10× faux le 2026-09-08 (+360 attribués à une
--      journée quand YouTube Studio en annonçait 64 sur la période). Affiché sur
--      « Data Wrapped » comme « YouTube — vues ».
--   3. `pdf_exporter/_collectors.py` → `MAX(view_count)` de la même table de chaîne,
--      imprimé dans le PDF client à côté du total corrigé venant de `platform_totals`.
--
-- Le même locataire lisait donc trois nombres différents au même instant, dont deux
-- faux, sur trois surfaces du même produit.
--
-- Pourquoi une VUE et pas une table matérialisée : ADR-019. Ces duplications vivent
-- dans des requêtes exécutées à la LECTURE ; matérialiser n'en retirerait aucune, et
-- créerait le graphe de dépendances dont ADR-014 a montré qu'il n'est pas justifié
-- (43 Mo, agrégat le plus lourd à 18,5 ms).
--
-- Le compteur de chaîne n'est pas supprimé : il reste lisible sur la page YouTube, où
-- il est LABELLÉ « Vues Totales (chaîne) » et ne côtoie aucune série qui le contredit.

CREATE OR REPLACE VIEW v_platform_totals AS
    -- Spotify for Artists : quantités du JOUR. Dédupliqué par (date, song) — deux
    -- imports du même jour ne doivent pas doubler les écoutes — et la ligne « Total »
    -- des CSV est écartée, règle transverse du dépôt.
    SELECT artist_id, 'spotify'::text AS platform,
           COALESCE(SUM(daily_max), 0)::bigint AS total
      FROM (
        SELECT artist_id, date, song, MAX(streams) AS daily_max
          FROM s4a_song_timeline
         WHERE artist_id IS NOT NULL AND song NOT ILIKE '%1x7xxxxxxx%'
         GROUP BY artist_id, date, song
      ) s
     GROUP BY artist_id

    UNION ALL

    -- YouTube : la somme des compteurs PAR VIDÉO, jamais celui de la chaîne. Le
    -- compteur de chaîne porte les vidéos privées, supprimées et des agrégats internes,
    -- et il avance par paliers.
    SELECT artist_id, 'youtube'::text,
           COALESCE(SUM(view_count), 0)::bigint
      FROM (
        SELECT DISTINCT ON (artist_id, video_id) artist_id, video_id, view_count
          FROM youtube_video_stats
         WHERE artist_id IS NOT NULL
         ORDER BY artist_id, video_id, collected_at DESC
      ) y
     GROUP BY artist_id

    UNION ALL

    -- SoundCloud : le dernier compteur cumulé connu de chaque titre.
    SELECT artist_id, 'soundcloud'::text,
           COALESCE(SUM(playback_count), 0)::bigint
      FROM (
        SELECT DISTINCT ON (artist_id, track_id) artist_id, track_id, playback_count
          FROM soundcloud_tracks_daily
         WHERE artist_id IS NOT NULL
         ORDER BY artist_id, track_id, collected_at DESC
      ) c
     GROUP BY artist_id;

COMMENT ON VIEW v_platform_totals IS
    'Couche OR (ADR-019) : le total « depuis le début » par locataire et par plateforme, '
    'une seule définition. Toute surface qui affiche ce nombre lit ICI. Apple suit sa '
    'propre règle (périodes imbriquées, non_overlapping_cover) et reste dans '
    'platform_timeseries.apple_lifetime_plays.';
