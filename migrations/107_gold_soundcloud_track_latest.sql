-- ═══════════════════════════════════════════════════════════════════════════
-- 107 — SoundCloud : le dernier relevé par titre, une seule fois
-- ═══════════════════════════════════════════════════════════════════════════
-- `soundcloud_tracks_daily` est un COMPTEUR : une ligne par (locataire, titre,
-- jour), dont la valeur ne redescend pas. Répondre « combien d'écoutes » veut
-- donc dire « le dernier relevé de chaque titre, puis la somme » — jamais la
-- somme des lignes.
--
-- Cette règle était recopiée en QUATRE endroits : la branche soundcloud de
-- `v_platform_totals` (097), et trois requêtes de `kpi_helpers.py` (les plays
-- par locataire, les plays de la flotte, les likes). Trois d'entre elles
-- portaient `DISTINCT ON (track_id)` SANS le locataire — deux artistes qui
-- repostent le même titre n'en gardaient donc qu'un seul. Le quatrième
-- (`v_platform_totals`) avait été corrigé ; les trois autres non. C'est la forme
-- exacte de la classe « une règle recopiée diverge ».
--
-- Et les LIKES n'avaient aucune vue or du tout : `v_platform_totals` ne porte
-- qu'une colonne `total`, donc la seule métrique SoundCloud couverte était les
-- écoutes. Une plateforme n'est pas « sur la couche or » tant qu'une de ses
-- mesures affichées vit ailleurs.
--
-- La vue porte les quatre compteurs de la table. `v_platform_totals` la lit au
-- lieu de refaire le `DISTINCT ON`, pour que la règle n'existe qu'ici.
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
           -- Un attribut, pas une mesure : la date de publication du titre. Elle
           -- est ici pour que la page SoundCloud n'ait aucune raison de retourner
           -- à la table brute juste pour la lire.
           track_created_at
      FROM soundcloud_tracks_daily
     WHERE artist_id IS NOT NULL
     ORDER BY artist_id, track_id, collected_at DESC;

COMMENT ON VIEW v_soundcloud_track_latest IS
    'Couche OR (ADR-019) : le dernier relevé de chaque titre SoundCloud, par '
    'locataire. SoundCloud est un COMPTEUR — toute somme se fait sur cette vue, '
    'jamais sur soundcloud_tracks_daily. Porte aussi les likes, que '
    'v_platform_totals ne peut pas exprimer (une seule colonne « total »).';

-- `v_platform_totals` cesse de redéclarer la règle. Les trois autres branches
-- sont réécrites à l'identique : `CREATE OR REPLACE VIEW` remplace la définition
-- entière, il n'y a pas de remplacement partiel.
CREATE OR REPLACE VIEW v_platform_totals AS
    SELECT artist_id, 'spotify'::text AS platform,
           COALESCE(SUM(streams), 0)::bigint AS total
      FROM v_s4a_song_daily
     GROUP BY artist_id
    UNION ALL
    SELECT artist_id, 'youtube'::text, COALESCE(SUM(view_count), 0)::bigint
      FROM (
        SELECT DISTINCT ON (artist_id, video_id) artist_id, video_id, view_count
          FROM youtube_video_stats WHERE artist_id IS NOT NULL
         ORDER BY artist_id, video_id, collected_at DESC
      ) y
     GROUP BY artist_id
    UNION ALL
    SELECT artist_id, 'soundcloud'::text, COALESCE(SUM(playback_count), 0)::bigint
      FROM v_soundcloud_track_latest
     GROUP BY artist_id
    UNION ALL
    SELECT a.artist_id, 'apple'::text, gold_apple_lifetime(a.artist_id, 'plays')
      FROM (SELECT DISTINCT artist_id FROM apple_songs_performance
             WHERE artist_id IS NOT NULL) a;
