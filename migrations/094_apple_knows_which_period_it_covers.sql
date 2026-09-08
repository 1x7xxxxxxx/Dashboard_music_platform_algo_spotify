-- 094 — Un relevé Apple sait QUELLE PÉRIODE il couvre.
--
-- Question posée le 2026-09-08 : « y a-t-il un intérêt de demander à l'artiste
-- d'importer les CSV de chaque année (2023, 2024, 2025) pour nos graphiques Apple
-- Music ? On pourrait du coup renseigner Apple avec un peu plus de précision ? »
--
-- Oui, et la migration 093 ne suffisait pas. Elle a donné à la table le droit de
-- garder plusieurs relevés ; il lui manquait de savoir CE QUE chacun mesure.
--
-- L'export Apple Music for Artists n'a AUCUNE colonne de date : c'est le sélecteur de
-- période de leur interface qui décide, et le fichier n'en garde pas la trace. Trois
-- exports annuels déposés le même jour se seraient donc écrasés (même `snapshot_date`),
-- et deux exports annuels distincts auraient été traités comme deux photos d'un cumul —
-- on aurait soustrait 2023 de 2024, ce qui n'a aucun sens : ce sont des périodes
-- DISJOINTES, pas des instantanés successifs.
--
-- D'où ces deux bornes, remplies par une question posée à l'artiste au dépôt (le même
-- mécanisme que la fenêtre 28 j / 12 mois des exports Spotify). `NULL` des deux côtés
-- signifie « depuis le début », qui reste le cas par défaut et celui des lignes déjà
-- présentes.

ALTER TABLE apple_songs_performance
    ADD COLUMN IF NOT EXISTS period_start DATE,
    ADD COLUMN IF NOT EXISTS period_end DATE;

-- La clé porte la période, pas seulement le jour du dépôt : déposer l'export 2023 puis
-- celui de 2024 le MÊME jour doit faire deux relevés, pas un écrasement.
--
-- `COALESCE` sur une date sentinelle parce qu'un index unique ignore les lignes dont
-- une colonne est NULL — sans lui, deux dépôts « depuis le début » ne se dédupliqueraient
-- plus du tout, et l'idempotence acquise en 093 serait perdue.
DROP INDEX IF EXISTS uq_apple_songs_perf_snapshot;

CREATE UNIQUE INDEX IF NOT EXISTS uq_apple_songs_perf_period
    ON apple_songs_performance (
        artist_id, song_name, snapshot_date,
        COALESCE(period_start, DATE '0001-01-01'),
        COALESCE(period_end,   DATE '0001-01-01')
    );

CREATE INDEX IF NOT EXISTS idx_apple_songs_perf_period
    ON apple_songs_performance (artist_id, period_start, period_end);
