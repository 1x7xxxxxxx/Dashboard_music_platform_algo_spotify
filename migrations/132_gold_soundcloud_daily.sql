-- ═══════════════════════════════════════════════════════════════════════════
-- 132 — SoundCloud au jour le jour, sans les collectes ratées
-- ═══════════════════════════════════════════════════════════════════════════
-- LE DÉFAUT, RAPPORTÉ PAR L'ARTISTE LE 2026-09-21
-- ------------------------------------------------
-- « Pourquoi il y a un bump le 1er juin sur chokbar de bezed […] il doit y avoir
-- un bug. » Il y en a un, et il est en base :
--
--     SELECT count(*) FROM soundcloud_tracks_daily
--      WHERE artist_id = 1 AND playback_count = 0;
--     → 19 lignes, TOUTES datées du 2026-06-01, et aucune autre date
--
-- Les 19 titres du catalogue étaient présents ce jour-là, tous à **zéro** sur les
-- quatre compteurs. Une collecte a répondu faux et le zéro a été ÉCRIT. Ces
-- compteurs sont CUMULÉS par titre : un cumul ne redescend pas, et surtout pas à
-- zéro sur tout un catalogue le même jour. Ce n'est pas une baisse d'audience,
-- c'est une panne persistée.
--
-- Conséquence à l'écran, exactement ce que l'artiste décrit : la courbe plonge à
-- zéro puis remonte — un « bump ». Et sur une base 100 dont le premier point sert
-- de référence, un zéro en tête ruine toute la série.
--
-- ⚠️ POURQUOI UNE VUE PLUTÔT QU'UN FILTRE DE PLUS. La règle « un cumul qui
-- redescend est une panne » était déjà appliquée — en PANDAS, dans
-- `views/soundcloud.py`, et seulement sur la figure base 100. La figure
-- principale, le tableau des tops et les tuiles ne l'avaient pas. Une règle
-- écrite dans une figure n'est pas une règle du produit : c'est la classe que ce
-- dépôt paie depuis des mois, et `v_s4a_song_daily` est né de la même leçon.
--
-- LA RÈGLE, ET CE QU'ELLE N'EST PAS
-- ----------------------------------
-- Un jour est écarté quand le total du catalogue y est STRICTEMENT INFÉRIEUR au
-- plus haut total déjà atteint. C'est plus large que « zéro », et délibérément :
-- un compteur qui passe de 23 486 à 12 000 est une panne tout autant qu'un zéro,
-- et le filtre `= 0` ne l'aurait pas vu.
--
-- Ce n'est PAS une correction de la donnée : les lignes brutes restent. La vue
-- dit seulement quels jours sont LISIBLES.
--
-- Mesuré le 2026-09-21 sur le locataire 1 : **19 jours de collecte, 1 écarté**
-- (le 2026-06-01). Le taux compte autant que le nombre — un filtre qui écarterait
-- la moitié des jours ne serait pas un filtre, ce serait un aveu.

CREATE OR REPLACE VIEW v_soundcloud_catalog_daily AS
    WITH par_jour AS (
        -- Un jour peut porter plusieurs horodatages : mesuré le 2026-09-10,
        -- **317 horodatages distincts pour 19 jours**, parce que les titres d'une
        -- même nuit ne sont pas écrits au même instant. On prend donc le DERNIER
        -- relevé de chaque titre dans la journée, puis on somme le catalogue.
        SELECT artist_id, date(collected_at) AS day, track_id,
               (ARRAY_AGG(playback_count ORDER BY collected_at DESC))[1] AS plays,
               (ARRAY_AGG(likes_count    ORDER BY collected_at DESC))[1] AS likes,
               (ARRAY_AGG(reposts_count  ORDER BY collected_at DESC))[1] AS reposts,
               (ARRAY_AGG(comment_count  ORDER BY collected_at DESC))[1] AS comments
          FROM soundcloud_tracks_daily
         GROUP BY artist_id, date(collected_at), track_id
    ), totaux AS (
        SELECT artist_id, day,
               COUNT(*)::int            AS tracks,
               SUM(plays)::bigint       AS plays,
               SUM(likes)::bigint       AS likes,
               SUM(reposts)::bigint     AS reposts,
               SUM(comments)::bigint    AS comments
          FROM par_jour
         GROUP BY artist_id, day
    )
    SELECT artist_id, day, tracks, plays, likes, reposts, comments,
           -- `lisible` : ce total est-il au moins égal au plus haut déjà vu ?
           -- Le `ROWS UNBOUNDED PRECEDING` inclut la ligne courante, donc le
           -- premier jour est lisible par construction.
           (plays >= MAX(plays) OVER (PARTITION BY artist_id ORDER BY day
                                      ROWS UNBOUNDED PRECEDING)) AS lisible
      FROM totaux;

COMMENT ON VIEW v_soundcloud_catalog_daily IS
    'Couche OR (ADR-019) : les quatre compteurs SoundCloud du CATALOGUE, au grain '
    '(locataire, jour). Un jour porte le DERNIER relevé de chaque titre — 317 '
    'horodatages pour 19 jours, mesuré. `lisible` est FAUX quand le cumul redescend '
    'sous son maximum : ce n''est pas une baisse d''audience, c''est une collecte '
    'ratée persistée (19 lignes à zéro le 2026-06-01, et aucune autre date). Les '
    'lignes brutes ne sont pas touchées — la vue dit seulement ce qui est lisible.';

-- ── LA LISIBILITÉ EST PAR MÉTRIQUE, et c'est une correction mesurée ─────────
--
-- Le premier jet appliquait UNE règle aux quatre compteurs : « un cumul qui
-- redescend est une panne ». Elle est juste pour les ÉCOUTES et fausse pour les
-- trois autres — **un like se retire, un repost s'annule, un commentaire
-- s'efface**. Mesuré sur « FEET FIRST » : les likes passent de 179 à 178, ce qui
-- est un désabonnement ordinaire, pas une panne.
--
-- Appliquée telle quelle en aval (filtre `cummax` en pandas), cette règle unique
-- écartait **10 relevés sur 18** — plus de la moitié de la série — parce qu'un
-- recul de 1 like disqualifiait tous les points suivants. Un filtre qui jette la
-- moitié de sa population ne nettoie pas une courbe, il la supprime.
--
-- LE ZÉRO, LUI, RESTE UNE PANNE POUR LES QUATRE. Un compteur à vie qui vaut
-- exactement 0 après avoir été positif n'est pas un geste d'auditeur : c'est une
-- lecture qui a échoué. Mesuré ici sur DEUX ères distinctes :
--
--     2026-06-01                 les 19 titres à 0 sur les 4 compteurs
--     2026-03-30 → 2026-05-14    `likes` à 0 seuls, avant la bascule OAuth
--
-- La seconde est une panne d'INSTRUMENT, pas d'un jour : la page l'annonçait déjà
-- en prose (« likes fiables depuis le 15/05/2026 »). Elle est maintenant dans la
-- donnée, donc toutes les surfaces la voient — et aucune n'a besoin de connaître
-- la date.

-- ── Le même verdict, au grain du TITRE ──────────────────────────────────────
--
-- La lisibilité se décide sur le CATALOGUE et non titre par titre, et c'est un
-- choix : un titre à 4 écoutes qui stagne est indiscernable, à son échelle, d'un
-- titre dont la collecte a échoué. Le total du catalogue, lui, tranche sans
-- ambiguïté — 19 titres à zéro le même jour n'est pas une coïncidence.
CREATE OR REPLACE VIEW v_soundcloud_track_daily AS
    SELECT p.artist_id, p.day, p.track_id, p.title,
           p.plays, p.likes, p.reposts, p.comments,
           c.lisible,
           -- Par MÉTRIQUE : ce zéro succède-t-il à une valeur positive sur le
           -- même titre ? Alors c'est une lecture ratée, pas un compteur remis à
           -- zéro par un auditeur.
           NOT (p.likes = 0 AND MAX(p.likes) OVER w > 0)     AS likes_lisibles,
           NOT (p.reposts = 0 AND MAX(p.reposts) OVER w > 0) AS reposts_lisibles,
           NOT (p.comments = 0 AND MAX(p.comments) OVER w > 0) AS comments_lisibles
      FROM (
            SELECT artist_id, date(collected_at) AS day, track_id,
                   (ARRAY_AGG(title           ORDER BY collected_at DESC))[1] AS title,
                   (ARRAY_AGG(playback_count  ORDER BY collected_at DESC))[1] AS plays,
                   (ARRAY_AGG(likes_count     ORDER BY collected_at DESC))[1] AS likes,
                   (ARRAY_AGG(reposts_count   ORDER BY collected_at DESC))[1] AS reposts,
                   (ARRAY_AGG(comment_count   ORDER BY collected_at DESC))[1] AS comments
              FROM soundcloud_tracks_daily
             GROUP BY artist_id, date(collected_at), track_id
           ) p
      JOIN v_soundcloud_catalog_daily c
        ON c.artist_id = p.artist_id AND c.day = p.day
    WINDOW w AS (PARTITION BY p.artist_id, p.track_id ORDER BY p.day
                 ROWS UNBOUNDED PRECEDING);

COMMENT ON VIEW v_soundcloud_track_daily IS
    'Couche OR (ADR-019) : les quatre compteurs SoundCloud au grain (locataire, '
    'titre, jour), avec le verdict `lisible` hérité du CATALOGUE. Le verdict se '
    'décide au catalogue à dessein : un titre à 4 écoutes qui stagne est '
    'indiscernable d''une collecte ratée à son échelle, le total ne l''est pas. '
    'likes/reposts/comments_lisibles est FAUX quand le compteur vaut 0 après avoir '
    'été positif — une lecture ratée. Ces trois-là PEUVENT décroître (un like se '
    'retire) : leur appliquer la règle des écoutes écartait 10 relevés sur 18.';
