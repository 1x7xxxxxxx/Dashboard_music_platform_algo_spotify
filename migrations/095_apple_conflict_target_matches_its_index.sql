-- 095 — La clé de conflit Apple doit être une clé que Postgres sait reconnaître.
--
-- Signalé le 2026-09-08, sur les CINQ fichiers annuels à la fois :
--
--     ❌ there is no unique or exclusion constraint matching the ON CONFLICT specification
--
-- C'est un défaut de la migration 094, et il est mécanique. Elle a créé un index unique
-- sur des EXPRESSIONS :
--
--     (artist_id, song_name, snapshot_date,
--      COALESCE(period_start, DATE '0001-01-01'),
--      COALESCE(period_end,   DATE '0001-01-01'))
--
-- alors que l'upsert désigne des COLONNES :
--
--     ON CONFLICT (artist_id, song_name, snapshot_date, period_start, period_end)
--
-- Postgres n'apparie une cible `ON CONFLICT` à un index que si les expressions
-- coïncident. Un index sur `COALESCE(col, …)` ne peut donc jamais servir de cible à une
-- liste de colonnes nues : la table avait bien sa contrainte d'unicité, et l'upsert ne
-- pouvait pas la voir.
--
-- Le `COALESCE` était là pour une VRAIE raison : un index unique ordinaire considère
-- deux NULL comme différents, donc deux relevés « depuis le début » (période NULL)
-- n'auraient plus été dédupliqués — l'idempotence acquise en 093 aurait été perdue.
--
-- PostgreSQL 15 a la réponse exacte, et la production tourne en 17.10 :
-- `NULLS NOT DISTINCT` rend deux NULL égaux DANS l'index, sans expression. La cible
-- redevient une liste de colonnes, l'upsert la trouve, et l'idempotence tient.

DROP INDEX IF EXISTS uq_apple_songs_perf_period;

CREATE UNIQUE INDEX IF NOT EXISTS uq_apple_songs_perf_period
    ON apple_songs_performance (
        artist_id, song_name, snapshot_date, period_start, period_end
    ) NULLS NOT DISTINCT;
