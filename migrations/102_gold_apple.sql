-- 102 — Apple entre dans la couche OR (R92).
--
-- C'était la dernière plateforme dont le total n'avait AUCUNE définition SQL : sa
-- règle vivait dans `platform_timeseries.apple_lifetime_plays`, et cinq fichiers
-- lisaient `apple_songs_performance` directement. Aujourd'hui pour lister — rien
-- n'empêchait le prochain de totaliser à sa façon, et c'est exactement ainsi que
-- YouTube a eu trois définitions avant la migration 097.
--
-- POURQUOI UNE FONCTION ET PAS UNE VUE. La règle Apple n'est pas un agrégat : elle
-- choisit entre trois formes de relevé, et l'une d'elles est une sélection GLOUTONNE
-- d'intervalles (garder les plus courts, écarter tout ce qui les chevauche). Un
-- `GROUP BY` ne l'exprime pas. La poser en PL/pgSQL la garde lisible et, surtout,
-- la garde à UN endroit — ADR-002 n'interdit que SQLAlchemy et Alembic, pas le SQL.
--
-- LES TROIS FORMES, par précision décroissante :
--   1. le relevé borné le plus LARGE — l'export « depuis le début », qui contient
--      déjà les années ;
--   2. la somme du découpage non chevauchant — l'export 2024 et l'export 2025
--      additionnés, mais jamais 2024 en plus d'un cumul qui le contient ;
--   3. à défaut de tout relevé borné, le dernier instantané sans bornes.
--
-- On rend le MAX de (1) et (2) : le découpage peut être plus complet que le cumul
-- quand une année manque à ce dernier.

CREATE OR REPLACE FUNCTION gold_apple_lifetime(p_artist_id integer)
RETURNS bigint
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    r            RECORD;
    kept_s       date[] := '{}';
    kept_e       date[] := '{}';
    cover_total  bigint := 0;
    widest_plays bigint := 0;
    widest_span  integer := -1;
    has_overlap  boolean;
    i            integer;
BEGIN
    -- Les plus COURTS d'abord : c'est ce qui rend le découpage le plus fin possible.
    FOR r IN
        SELECT period_start AS s, period_end AS e,
               COALESCE(SUM(plays), 0)::bigint AS p
          FROM apple_songs_performance
         WHERE artist_id = p_artist_id
           AND period_start IS NOT NULL AND period_end IS NOT NULL
         GROUP BY period_start, period_end
         ORDER BY (period_end - period_start) ASC, period_start ASC
    LOOP
        -- (1) le plus large, départagé par les écoutes — comme le fait le Python.
        IF (r.e - r.s) > widest_span
           OR ((r.e - r.s) = widest_span AND r.p > widest_plays) THEN
            widest_span  := r.e - r.s;
            widest_plays := r.p;
        END IF;

        -- (2) le découpage non chevauchant.
        has_overlap := FALSE;
        FOR i IN 1 .. COALESCE(array_length(kept_s, 1), 0) LOOP
            IF r.s <= kept_e[i] AND kept_s[i] <= r.e THEN
                has_overlap := TRUE;
                EXIT;
            END IF;
        END LOOP;
        IF NOT has_overlap THEN
            kept_s := kept_s || r.s;
            kept_e := kept_e || r.e;
            cover_total := cover_total + r.p;
        END IF;
    END LOOP;

    IF widest_span >= 0 THEN
        RETURN GREATEST(widest_plays, cover_total);
    END IF;

    -- (3) aucun relevé borné : le dernier instantané.
    RETURN COALESCE((
        SELECT COALESCE(SUM(plays), 0)::bigint
          FROM apple_songs_performance
         WHERE artist_id = p_artist_id AND period_start IS NULL
           AND snapshot_date = (SELECT MAX(snapshot_date)
                                  FROM apple_songs_performance
                                 WHERE artist_id = p_artist_id
                                   AND period_start IS NULL)
    ), 0);
END;
$$;

COMMENT ON FUNCTION gold_apple_lifetime(integer) IS
    'Couche OR (ADR-019) : le total Apple « depuis le début », une définition et une '
    'seule. Trois formes par précision décroissante — relevé borné le plus large, '
    'découpage non chevauchant des années, dernier instantané sans bornes.';

-- La vue or gagne sa quatrième plateforme. `v_platform_totals` conserve exactement
-- ses trois branches existantes ; Apple s'y ajoute, une ligne par locataire qui a
-- au moins un relevé.
CREATE OR REPLACE VIEW v_platform_totals AS
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

    SELECT artist_id, 'soundcloud'::text,
           COALESCE(SUM(playback_count), 0)::bigint
      FROM (
        SELECT DISTINCT ON (artist_id, track_id) artist_id, track_id, playback_count
          FROM soundcloud_tracks_daily
         WHERE artist_id IS NOT NULL
         ORDER BY artist_id, track_id, collected_at DESC
      ) c
     GROUP BY artist_id

    UNION ALL

    -- Apple : la règle est dans la fonction, jamais recopiée ici.
    SELECT a.artist_id, 'apple'::text, gold_apple_lifetime(a.artist_id)
      FROM (SELECT DISTINCT artist_id FROM apple_songs_performance
             WHERE artist_id IS NOT NULL) a;
