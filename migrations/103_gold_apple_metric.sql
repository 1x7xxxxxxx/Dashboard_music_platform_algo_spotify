-- 103 — La règle Apple vaut pour ses DEUX métriques (R92, suite).
--
-- `gold_apple_lifetime` (migration 102) portait la règle pour `plays`. Les SHAZAMS
-- suivent exactement la même — relevé borné le plus large, sinon découpage non
-- chevauchant, sinon dernier instantané — et `views/apple_music.py` la recopiait en
-- Python, avec sa propre branche `if/else`. Deux copies d'un même algorithme, dont
-- une seule était testée.
--
-- La métrique devient donc un PARAMÈTRE, jamais un second corps de fonction. Elle
-- est validée contre une allowlist avant d'entrer dans du SQL dynamique : c'est la
-- règle transverse #8 du dépôt, et ici elle n'est pas théorique — `p_metric` finirait
-- littéralement dans un `SUM(...)`.

CREATE OR REPLACE FUNCTION gold_apple_lifetime(p_artist_id integer,
                                               p_metric text DEFAULT 'plays')
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
    fallback     bigint;
BEGIN
    IF p_metric NOT IN ('plays', 'shazam_count') THEN
        RAISE EXCEPTION 'gold_apple_lifetime: métrique inconnue %', p_metric
            USING HINT = 'plays ou shazam_count';
    END IF;

    FOR r IN EXECUTE format(
        'SELECT period_start AS s, period_end AS e, '
        '       COALESCE(SUM(%I), 0)::bigint AS p '
        '  FROM apple_songs_performance '
        ' WHERE artist_id = $1 '
        '   AND period_start IS NOT NULL AND period_end IS NOT NULL '
        ' GROUP BY period_start, period_end '
        ' ORDER BY (period_end - period_start) ASC, period_start ASC', p_metric)
        USING p_artist_id
    LOOP
        IF (r.e - r.s) > widest_span
           OR ((r.e - r.s) = widest_span AND r.p > widest_plays) THEN
            widest_span  := r.e - r.s;
            widest_plays := r.p;
        END IF;

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

    EXECUTE format(
        'SELECT COALESCE(SUM(%I), 0)::bigint FROM apple_songs_performance '
        ' WHERE artist_id = $1 AND period_start IS NULL '
        '   AND snapshot_date = (SELECT MAX(snapshot_date) '
        '                          FROM apple_songs_performance '
        '                         WHERE artist_id = $1 AND period_start IS NULL)',
        p_metric)
        USING p_artist_id INTO fallback;
    RETURN COALESCE(fallback, 0);
END;
$$;

COMMENT ON FUNCTION gold_apple_lifetime(integer, text) IS
    'Couche OR (ADR-019) : le total Apple « depuis le début » pour plays ou '
    'shazam_count. Même règle à trois branches pour les deux — relevé borné le plus '
    'large, découpage non chevauchant, dernier instantané.';

-- ⚠️ L'ORDRE COMPTE, et il a coûté deux essais.
--
-- `gold_apple_lifetime(integer)` de la migration 102 et la version à deux arguments
-- (dont le second a un défaut) matchent TOUTES DEUX un appel à un seul argument :
-- Postgres rend alors `AmbiguousFunction`, la lecture échoue, et `apple_lifetime_plays`
-- dégrade en 0. Mesuré au premier rendu, le 2026-09-12 : la tuile « Total Streams »
-- affichait **0** pendant que « Total Shazams » affichait 1 770. Une erreur avalée par
-- un `except` qui protège la page devient un zéro affirmé.
--
-- L'ancienne ne peut pas être retirée avant que la vue cesse d'en dépendre. Donc :
-- la nouvelle existe (ci-dessus), la vue la nomme explicitement (ici), l'ancienne
-- part (en dernier).
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
    SELECT artist_id, 'youtube'::text, COALESCE(SUM(view_count), 0)::bigint
      FROM (
        SELECT DISTINCT ON (artist_id, video_id) artist_id, video_id, view_count
          FROM youtube_video_stats WHERE artist_id IS NOT NULL
         ORDER BY artist_id, video_id, collected_at DESC
      ) y
     GROUP BY artist_id
    UNION ALL
    SELECT artist_id, 'soundcloud'::text, COALESCE(SUM(playback_count), 0)::bigint
      FROM (
        SELECT DISTINCT ON (artist_id, track_id) artist_id, track_id, playback_count
          FROM soundcloud_tracks_daily WHERE artist_id IS NOT NULL
         ORDER BY artist_id, track_id, collected_at DESC
      ) c
     GROUP BY artist_id
    UNION ALL
    SELECT a.artist_id, 'apple'::text, gold_apple_lifetime(a.artist_id, 'plays')
      FROM (SELECT DISTINCT artist_id FROM apple_songs_performance
             WHERE artist_id IS NOT NULL) a;

DROP FUNCTION IF EXISTS gold_apple_lifetime(integer);
