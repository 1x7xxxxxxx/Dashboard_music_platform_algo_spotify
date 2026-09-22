-- ═══════════════════════════════════════════════════════════════════════════
-- 131 — La série Apple d'un titre, et la table morte qu'elle remplace
-- ═══════════════════════════════════════════════════════════════════════════
-- LE DÉFAUT, RAPPORTÉ PAR L'ARTISTE LE 2026-09-21
-- ------------------------------------------------
-- « J'avais pourtant download les derniers csv de apple music mais j'ai l'info
-- "Aucune mesure Apple Music sur cette période. La dernière remonte au
-- 2025-12-11". »
--
-- Il avait raison, et le message aussi : les deux décrivaient des TABLES
-- DIFFÉRENTES.
--
--     apple_songs_history      2 relevés · 2025-11-29 → 2025-12-11
--     apple_songs_performance  1 relevé  · 2026-06-08          ← ses imports
--
-- L'import CSV écrit `apple_songs_performance` (`utils/csv_platforms.py`).
-- **RIEN n'écrit `apple_songs_history`** — vérifié sur tout l'arbre le
-- 2026-09-21 : la table est DÉCLARÉE (`apple_music_csv_schema.py`), autorisée
-- (`postgres_handler.py`), LUE par trois surfaces (la croissance quotidienne de
-- la page Apple, le graphe quotidien du PDF, la fraîcheur de la page admin) et
-- écrite par personne. `tools/tenant_contamination_check.py:147` l'étiquette même
-- « Apple Music CSV upload » — la croyance était écrite, elle était fausse.
--
-- Classe : `a-table-that-is-read-and-no-longer-written`. Elle ne lève jamais :
-- une table vide se lit comme « pas encore de données », et ici elle se lisait
-- comme « ton import n'est pas arrivé ».
--
-- LES DEUX TABLES PORTENT LE MÊME FAIT, ET C'EST MESURÉ
-- ------------------------------------------------------
-- Ce n'est pas une supposition : les valeurs se suivent, par titre, à travers les
-- deux tables (locataire 1, 2026-09-21) —
--
--     « Je ne parle pas très bien le français »   524 → 526 → 562
--     « Qui a bu le crachoir du saloon ? »        434 → 436 → 477
--          (history 29/11)  (history 11/12)  (performance 08/06)
--
-- Même grandeur, même unité, monotone croissante : un CUMUL à vie par titre. Les
-- réunir reconstruit la série que ni l'une ni l'autre ne porte seule. Écarter
-- l'ancienne table ferait perdre deux relevés réels ; ne lire qu'elle, c'est le
-- défaut d'aujourd'hui.
--
-- ⚠️ CE SONT DES CUMULS, PAS DES QUANTITÉS QUOTIDIENNES. La vue du dessous en
-- prend la DIFFÉRENCE (`LAG`). Tracer le cumul comme un quotidien est la classe
-- `cumulative-counter-drawn-as-its-own-history`, mesurée à ×870 et ×306 dans ce
-- dépôt sur YouTube et SoundCloud.

CREATE OR REPLACE VIEW v_apple_song_cumulative AS
    -- L'UNION des deux sources, la table VIVANTE gagnant en cas d'égalité de
    -- (titre, jour). Elles ne se chevauchent pas aujourd'hui ; la règle existe
    -- pour le jour où un import sera déposé à une date déjà présente dans
    -- l'ancienne table, et pour qu'on n'ait pas à deviner alors.
    SELECT DISTINCT ON (artist_id, song_name, day)
           artist_id, song_name, day, plays, shazam_count, listeners, source
      FROM (
            SELECT artist_id, song_name, snapshot_date AS day,
                   plays::bigint, shazam_count::bigint, listeners::bigint,
                   'csv_import'::text AS source, 0 AS priorite
              FROM apple_songs_performance
             WHERE snapshot_date IS NOT NULL
            UNION ALL
            SELECT artist_id, song_name, date AS day,
                   plays::bigint, shazam_count::bigint, NULL::bigint,
                   'legacy_history'::text, 1
              FROM apple_songs_history
             WHERE date IS NOT NULL
           ) u
     ORDER BY artist_id, song_name, day, priorite;

COMMENT ON VIEW v_apple_song_cumulative IS
    'Couche OR (ADR-019) : le cumul à vie Apple (écoutes, Shazams) au grain '
    '(locataire, titre, jour de relevé). Réunit la table VIVANTE '
    '(apple_songs_performance, écrite par l''import CSV) et la table MORTE '
    '(apple_songs_history, lue par trois surfaces et écrite par rien depuis des '
    'mois) — les deux portent le même cumul, vérifié valeur par valeur le '
    '2026-09-21. Ce sont des CUMULS : v_apple_song_daily en prend la différence.';

-- ── La quantité QUOTIDIENNE, dérivée du cumul ───────────────────────────────
--
-- `LAG` sur la série du titre. Le premier relevé n'a pas de prédécesseur : sa
-- différence est NULL, jamais 0 — « on ne sait pas ce qui s'est passé avant »
-- n'est pas « il ne s'est rien passé ». C'est la règle que la migration 113 a
-- rétablie pour le total, et elle vaut ici.
--
-- `days_since_previous` est RENDU, et c'est ce qui permet à la surface de ne pas
-- mentir : deux relevés espacés de six mois donnent une « croissance
-- quotidienne » qui est en fait la croissance d'un semestre. La figure doit le
-- dire, donc la vue doit le fournir.
CREATE OR REPLACE VIEW v_apple_song_daily AS
    SELECT artist_id, song_name, day,
           plays, shazam_count,
           (plays - LAG(plays) OVER w)::bigint               AS daily_plays,
           (shazam_count - LAG(shazam_count) OVER w)::bigint AS daily_shazams,
           (day - LAG(day) OVER w)::int                      AS days_since_previous
      FROM v_apple_song_cumulative
    WINDOW w AS (PARTITION BY artist_id, song_name ORDER BY day);

COMMENT ON VIEW v_apple_song_daily IS
    'Couche OR (ADR-019) : la quantité gagnée entre deux relevés Apple, par titre. '
    'Le premier relevé rend NULL et jamais 0 — une absence de prédécesseur n''est '
    'pas une absence d''écoute. days_since_previous est rendu pour que la surface '
    'puisse dire sur COMBIEN de jours la quantité a été gagnée : deux relevés à six '
    'mois d''écart ne décrivent pas une journée.';
