-- ═══════════════════════════════════════════════════════════════════════════
-- 142 — Shazams et écoutes Apple QUOTIDIENS, depuis un export d'un jour (R235)
-- ═══════════════════════════════════════════════════════════════════════════
--
-- La question du propriétaire (2026-09-27) : « pour Shazam, si on fait le relevé CSV
-- journalier, on pourrait y accéder ? ». Oui, à une condition que le schéma ignorait :
-- un export Apple Music for Artists couvre la PÉRIODE choisie dans leur interface,
-- écrite dans le nom du fichier et stockée en `period_start` / `period_end` depuis
-- l'import. La vue 131 traitait chaque ligne comme un cumul À VIE et en prenait la
-- différence : deux exports de périodes différentes se soustrayaient (2024 − 2023).
--
-- Deux façons honnêtes d'obtenir le quotidien, et cette migration sert les deux :
--
-- 1. **Un export d'UN jour** (`period_start = period_end`) — le fichier EST la
--    quantité du jour, par titre : écoutes et Shazams directement, sans soustraction.
--    C'est le geste recommandé pendant une campagne : exporter « hier » chaque matin.
-- 2. **Des exports cumulés de même origine** (même `period_start`, ou sans période
--    comme les imports d'avant) — la différence de deux relevés consécutifs, comme
--    en 131, mais PAR ORIGINE : on ne soustrait plus deux périodes différentes.
--
-- Le relevé est daté par la FIN de la période exportée (import, R235), plus par le
-- jour du dépôt : un export d'hier déposé ce matin décrit hier.

CREATE OR REPLACE VIEW v_apple_song_cumulative AS
    -- Les exports d'UN jour ne sont pas des cumuls : ils sortent de cette vue et
    -- entrent directement dans la série quotidienne ci-dessous.
    SELECT DISTINCT ON (artist_id, song_name, day)
           artist_id, song_name, day, plays, shazam_count, listeners, source
      FROM (
            SELECT artist_id, song_name, snapshot_date AS day,
                   plays::bigint, shazam_count::bigint, listeners::bigint,
                   'csv_import'::text AS source, 0 AS priorite
              FROM apple_songs_performance
             WHERE snapshot_date IS NOT NULL
               AND NOT (period_start IS NOT NULL AND period_start = period_end)
            UNION ALL
            SELECT artist_id, song_name, date AS day,
                   plays::bigint, shazam_count::bigint, NULL::bigint,
                   'legacy_history'::text, 1
              FROM apple_songs_history
             WHERE date IS NOT NULL
           ) u
     ORDER BY artist_id, song_name, day, priorite;

CREATE OR REPLACE VIEW v_apple_song_daily AS
    -- (2) les cumuls, différenciés PAR ORIGINE de période
    SELECT artist_id, song_name, day, plays, shazam_count,
           (plays - LAG(plays) OVER w)::bigint               AS daily_plays,
           (shazam_count - LAG(shazam_count) OVER w)::bigint AS daily_shazams,
           (day - LAG(day) OVER w)::int                      AS days_since_previous
      FROM (
            SELECT c.artist_id, c.song_name, c.day, c.plays, c.shazam_count,
                   COALESCE(p.period_start, DATE '1900-01-01') AS origine
              FROM v_apple_song_cumulative c
              LEFT JOIN apple_songs_performance p
                ON p.artist_id = c.artist_id AND p.song_name = c.song_name
               AND p.snapshot_date = c.day AND c.source = 'csv_import'
           ) cum
    WINDOW w AS (PARTITION BY artist_id, song_name, origine ORDER BY day)
    UNION ALL
    -- (1) les exports d'UN jour : la quantité du jour, telle quelle
    SELECT artist_id, song_name, period_end AS day,
           NULL::bigint, NULL::bigint,
           plays::bigint, shazam_count::bigint, 1
      FROM apple_songs_performance
     WHERE period_start IS NOT NULL AND period_start = period_end;

COMMENT ON VIEW v_apple_song_daily IS
    'Couche OR (ADR-019) : écoutes et Shazams Apple QUOTIDIENS par titre. Deux sources : '
    'un export d''un jour (period_start = period_end), pris tel quel ; et la différence de '
    'deux cumuls de même origine de période. Le premier relevé d''une origine rend NULL, '
    'jamais 0 ; days_since_previous dit sur combien de jours la quantité a été gagnée '
    '(migrations 131, 142).';
