-- 104 — La couche OR gagne son GRAIN TEMPOREL (R94, préalable).
--
-- `v_platform_totals` répond « combien au total ». Elle ne répond pas « combien sur
-- cette période », et c'est ce trou qui laissait 58 agrégats hors couche or : une
-- requête bornée par une fenêtre ne pouvait pas la lire, donc chaque surface
-- recalculait la sienne. Trois défauts en sont sortis le 2026-09-11, dont un facteur
-- 887 imprimé sur la même page de PDF que la courbe qui le contredisait.
--
-- CE QUE CETTE VUE PORTE : le NIVEAU de chaque plateforme à chaque jour — le compteur
-- tel qu'il était ce jour-là. Tout le reste s'en dérive, et c'est le point :
--
--     total depuis le début   = niveau au dernier jour
--     croissance sur [a, b]   = niveau(b) − niveau(juste avant a)
--     quantité du jour j      = niveau(j) − niveau(j−1)
--
-- Une seule définition, trois questions. C'est la `metrics layer` de Reis & Housley
-- (Fundamentals of Data Engineering, p. 482), et la raison pour laquelle les trois
-- défauts ci-dessus étaient trois façons de répondre à la même question.
--
-- LE REPORT EN AVANT est ce qui rend l'égalité vraie par construction : une vidéo non
-- relevée un jour garde sa dernière valeur connue au lieu de disparaître de la somme.
-- Sans lui, la courbe plonge les jours de collecte partielle — YouTube n'est mesurée
-- que 39 % des jours — et son dernier point ne vaut le total que par chance.
--
-- POURQUOI UNE VUE : ADR-014. 62 Mo, tout tient en cache, `read=0`. Mesurée à **16 ms**
-- sur la base locale. Matérialiser créerait un graphe de dépendances contre un gain nul.
--
-- APPLE N'Y EST PAS, et c'est dit plutôt que sous-entendu : ses exports sont des
-- totaux de PÉRIODE, pas des relevés quotidiens. Lui inventer un niveau par jour
-- étalerait 900 écoutes sur 366 journées que personne n'a mesurées. Elle garde
-- `gold_apple_lifetime()` et n'apparaît qu'au pas annuel.

CREATE OR REPLACE VIEW v_platform_levels AS
    -- ── SPOTIFY : quantités quotidiennes, donc le niveau est leur somme courante.
    WITH sp_day AS (
        SELECT artist_id, date AS j, SUM(daily_max)::bigint AS q
          FROM (
            SELECT artist_id, date, song, MAX(streams) AS daily_max
              FROM s4a_song_timeline
             WHERE artist_id IS NOT NULL AND song NOT ILIKE '%1x7xxxxxxx%'
             GROUP BY artist_id, date, song
          ) d
         GROUP BY artist_id, date
    ),
    -- ── YOUTUBE : compteur par vidéo, reporté en avant.
    -- ⚠️ `> 0`, PAS `IS NOT NULL`. Une collecte ratée écrit des ZÉROS, pas des NULL,
    -- et un compteur ne redescend pas à zéro une fois positif. Mesuré le 2026-09-12 :
    -- le 2026-06-01, les 19 titres SoundCloud de l'artiste 1 sont tous à 0 alors que
    -- la veille et le lendemain donnent 3 794 — le niveau s'effondrait de 23 475 à 0
    -- puis remontait, et la courbe montrait une perte totale qui n'a pas eu lieu.
    -- `pdf_exporter/_collectors.py` connaissait déjà ce piège (« skip anomalous
    -- zero-playback snapshots ») ; la couche or l'ignorait.
    --
    -- Ce que ce filtre coûte, et qui est assumé : un titre réellement à zéro écoute
    -- n'apparaît qu'à partir de son premier relevé non nul. C'est la même chose que
    -- de ne pas le connaître, et l'alternative est de croire une panne de collecte.
    yt AS (
        SELECT artist_id, video_id, collected_at::date AS j, MAX(view_count) AS vc
          FROM youtube_video_stats
         WHERE artist_id IS NOT NULL AND view_count > 0
         GROUP BY 1, 2, 3
    ),
    yt_filled AS (
        SELECT g.artist_id, g.video_id, g.j, p.vc,
               COUNT(p.vc) OVER (PARTITION BY g.artist_id, g.video_id ORDER BY g.j) AS grp
          FROM (SELECT e.artist_id, e.video_id, d.j
                  FROM (SELECT DISTINCT artist_id, video_id FROM yt) e
                  JOIN (SELECT DISTINCT artist_id, j FROM yt) d
                    ON d.artist_id = e.artist_id) g
          LEFT JOIN yt p ON p.artist_id = g.artist_id
                        AND p.video_id = g.video_id AND p.j = g.j
    ),
    -- ── SOUNDCLOUD : compteur par titre, même forme.
    sc AS (
        SELECT artist_id, track_id, collected_at::date AS j,
               MAX(playback_count) AS vc
          FROM soundcloud_tracks_daily
         WHERE artist_id IS NOT NULL AND playback_count > 0
         GROUP BY 1, 2, 3
    ),
    sc_filled AS (
        SELECT g.artist_id, g.track_id, g.j, p.vc,
               COUNT(p.vc) OVER (PARTITION BY g.artist_id, g.track_id ORDER BY g.j) AS grp
          FROM (SELECT e.artist_id, e.track_id, d.j
                  FROM (SELECT DISTINCT artist_id, track_id FROM sc) e
                  JOIN (SELECT DISTINCT artist_id, j FROM sc) d
                    ON d.artist_id = e.artist_id) g
          LEFT JOIN sc p ON p.artist_id = g.artist_id
                        AND p.track_id = g.track_id AND p.j = g.j
    )
    SELECT artist_id, 'spotify'::text AS platform, j AS day,
           SUM(q) OVER (PARTITION BY artist_id ORDER BY j)::bigint AS level
      FROM sp_day

    UNION ALL

    SELECT artist_id, 'youtube'::text, j, SUM(vc)::bigint
      FROM (SELECT artist_id, j,
                   MAX(vc) OVER (PARTITION BY artist_id, video_id, grp) AS vc
              FROM yt_filled) c
     WHERE vc IS NOT NULL
     GROUP BY artist_id, j

    UNION ALL

    SELECT artist_id, 'soundcloud'::text, j, SUM(vc)::bigint
      FROM (SELECT artist_id, j,
                   MAX(vc) OVER (PARTITION BY artist_id, track_id, grp) AS vc
              FROM sc_filled) c
     WHERE vc IS NOT NULL
     GROUP BY artist_id, j;

COMMENT ON VIEW v_platform_levels IS
    'Couche OR (ADR-019) : le NIVEAU de chaque plateforme à chaque jour. Le total '
    'depuis le début est le dernier niveau ; la croissance sur une fenêtre est une '
    'différence de niveaux ; la quantité du jour est la différence avec la veille. '
    'Une définition, trois questions. Apple en est absente — ses exports sont des '
    'totaux de période, pas des relevés quotidiens.';
