-- ═══════════════════════════════════════════════════════════════════════════
-- 112 — Un relevé PARTIEL n'est pas un niveau
-- ═══════════════════════════════════════════════════════════════════════════
-- ⚠️ DÉFAUT VIVANT, mesuré le 2026-09-12 sur l'artiste 471.
--
-- Le 2026-08-20, la collecte YouTube a écrit **1 vidéo sur 200**. Le niveau de ce
-- jour vaut donc **5 vues** là où le lendemain, sur 200 vidéos, il vaut **33 490 844**.
-- Ce 5 n'est pas faux au sens des données — cette vidéo avait bien 5 vues — il est
-- faux en tant que NIVEAU DU LOCATAIRE, et il devient la ligne de base de tout ce
-- qui se calcule ensuite.
--
-- Conséquence mesurée : la figure « par semaine » totalisait 11 053 là où le
-- compteur a gagné 33 697 394. **Facteur 3 049.**
--
-- `is_partial_collection` (pilier Volume, R39) connaît déjà cette forme — il compte
-- les LIGNES écrites par une collecte. La couche or, elle, ne la connaissait pas :
-- elle voyait un jour avec des lignes valides et en faisait un niveau.
--
-- LE SEUIL EST CALIBRÉ, PAS CHOISI
-- --------------------------------
-- Distribution réelle du nombre d'entités par (locataire, jour) rapporté à la
-- MÉDIANE du locataire, sur les 60 jours-locataires des deux plateformes à
-- compteur, le 2026-09-12 :
--
--     < 10 %   →  1 jour   ← l'incident, et lui seul
--     10-50 %  →  0
--     50-90 %  →  6 jours  ← rotation légitime de catalogue
--     >= 90 %  → 53 jours
--
-- Un seuil à 10 % isole donc l'incident et ne touche rien d'autre. À 50 % il
-- resterait juste ; à 90 % il jetterait six jours de données vraies. Ce dépôt a une
-- classe pour le seuil écrit d'instinct — celui-ci est lu dans la distribution, et
-- la distribution est épinglée ici pour qu'on puisse la rejouer.
--
-- La MÉDIANE et non la moyenne : un seul jour à 1 vidéo sur 200 tire une moyenne
-- vers le bas et se protège lui-même. C'est Kleppmann sur les percentiles (DDIA
-- p. 37), appliqué au comptage plutôt qu'à la latence.
--
-- Ce que le filtre coûte : un locataire dont le catalogue passe réellement de 200 à
-- 15 titres verrait ses jours à 15 écartés jusqu'à ce que la médiane suive. C'est
-- assumé — l'alternative mesurée est un facteur 3 049 sur la figure principale.

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
    yt_raw AS (
        SELECT artist_id, video_id, collected_at::date AS j, MAX(view_count) AS vc
          FROM youtube_video_stats
         WHERE artist_id IS NOT NULL AND view_count > 0
         GROUP BY 1, 2, 3
    ),
    -- ⚠️ UN RELEVÉ PARTIEL N'EST PAS UN NIVEAU. Voir l'en-tête de la migration 112.
    -- Les jours RETENUS comme points de la courbe. Le filtre porte sur l'AXE, pas
    -- sur le pool de mesures : une entité vue UNIQUEMENT pendant une collecte
    -- partielle reste comptée à partir du jour suivant, par report en avant.
    --
    -- La première version retirait les lignes entières, et l'invariant
    -- `levels_vs_total_youtube` l'a attrapée dans la minute : une vidéo vue le seul
    -- jour partiel disparaissait des niveaux alors que `v_platform_totals` la
    -- comptait encore. Écart de 5 vues, trouvé par une égalité écrite une heure plus
    -- tôt — c'est exactement ce pour quoi elle existe.
    yt_days AS (
        SELECT c.artist_id, c.j FROM
          (SELECT artist_id, j, count(*) AS n FROM yt_raw GROUP BY 1, 2) c
          JOIN (SELECT artist_id,
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY n) AS med
                  FROM (SELECT artist_id, j, count(*) AS n FROM yt_raw GROUP BY 1, 2) x
                 GROUP BY 1) m
            ON m.artist_id = c.artist_id
         WHERE m.med IS NULL OR m.med = 0 OR c.n >= 0.10 * m.med
    ),
    yt AS (SELECT * FROM yt_raw),
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
    sc_raw AS (
        SELECT artist_id, track_id, collected_at::date AS j,
               MAX(playback_count) AS vc
          FROM soundcloud_tracks_daily
         WHERE artist_id IS NOT NULL AND playback_count > 0
         GROUP BY 1, 2, 3
    ),
    -- Les jours RETENUS comme points de la courbe. Le filtre porte sur l'AXE, pas
    -- sur le pool de mesures : une entité vue UNIQUEMENT pendant une collecte
    -- partielle reste comptée à partir du jour suivant, par report en avant.
    --
    -- La première version retirait les lignes entières, et l'invariant
    -- `levels_vs_total_youtube` l'a attrapée dans la minute : une vidéo vue le seul
    -- jour partiel disparaissait des niveaux alors que `v_platform_totals` la
    -- comptait encore. Écart de 5 vues, trouvé par une égalité écrite une heure plus
    -- tôt — c'est exactement ce pour quoi elle existe.
    sc_days AS (
        SELECT c.artist_id, c.j FROM
          (SELECT artist_id, j, count(*) AS n FROM sc_raw GROUP BY 1, 2) c
          JOIN (SELECT artist_id,
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY n) AS med
                  FROM (SELECT artist_id, j, count(*) AS n FROM sc_raw GROUP BY 1, 2) x
                 GROUP BY 1) m
            ON m.artist_id = c.artist_id
         WHERE m.med IS NULL OR m.med = 0 OR c.n >= 0.10 * m.med
    ),
    sc AS (SELECT * FROM sc_raw),
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

    -- Le report en avant court sur TOUS les jours, y compris les partiels : une
    -- vidéo vue seulement ce jour-là doit continuer d'être comptée ensuite. Seul
    -- l'AFFICHAGE est restreint aux jours retenus — un jour partiel n'est pas un
    -- point de la courbe, mais ses mesures ne sont pas perdues.
    SELECT c.artist_id, 'youtube'::text, c.j, SUM(c.vc)::bigint
      FROM (SELECT artist_id, video_id, j,
                   MAX(vc) OVER (PARTITION BY artist_id, video_id, grp) AS vc
              FROM yt_filled) c
      JOIN yt_days k ON k.artist_id = c.artist_id AND k.j = c.j
     WHERE c.vc IS NOT NULL
     GROUP BY c.artist_id, c.j

    UNION ALL

    SELECT c.artist_id, 'soundcloud'::text, c.j, SUM(c.vc)::bigint
      FROM (SELECT artist_id, track_id, j,
                   MAX(vc) OVER (PARTITION BY artist_id, track_id, grp) AS vc
              FROM sc_filled) c
      JOIN sc_days k ON k.artist_id = c.artist_id AND k.j = c.j
     WHERE c.vc IS NOT NULL
     GROUP BY c.artist_id, c.j;

COMMENT ON VIEW v_platform_levels IS
    'Couche OR (ADR-019) : le NIVEAU de chaque plateforme à chaque jour. Le total '
    'depuis le début est le dernier niveau ; la croissance sur une fenêtre est une '
    'différence de niveaux ; la quantité du jour est la différence avec la veille. '
    'Une définition, trois questions. Apple en est absente — ses exports sont des '
    'totaux de période, pas des relevés quotidiens.';
