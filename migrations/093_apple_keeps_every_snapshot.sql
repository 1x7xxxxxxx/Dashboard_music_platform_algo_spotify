-- 093 — Apple Music garde CHAQUE relevé, au lieu d'écraser le précédent.
--
-- Signalé le 2026-09-08 : « pour Apple je ne comprends pas, on devrait avoir
-- l'affichage, je viens de refaire le process avec le CSV d'aujourd'hui et rien ne
-- s'est actualisé ».
--
-- La cause est dans la clé, et elle est structurelle : `UNIQUE(artist_id, song_name)`.
-- Chaque dépôt de CSV ÉCRASE la ligne du même titre. La table n'a donc jamais porté
-- plus d'un relevé par artiste — mesuré le même jour : 11 lignes pour l'artiste 1,
-- toutes au même horodatage — et aucune période ne pouvait être découpée, pas plus
-- qu'un chiffre ne pouvait bouger si le CSV redéposé contenait les mêmes valeurs.
--
-- Ce n'était pas « Apple ne fournit pas de série » comme l'app le disait : c'est nous
-- qui n'en gardions aucune.
--
-- La clé gagne donc la DATE du relevé. Deux dépôts le même jour restent un seul relevé
-- — c'est voulu : re-déposer le même export deux fois de suite ne crée pas deux points.

ALTER TABLE apple_songs_performance
    ADD COLUMN IF NOT EXISTS snapshot_date DATE;

-- Les lignes existantes prennent la date de leur collecte. Elles forment le premier
-- relevé, celui qui existait déjà.
UPDATE apple_songs_performance
   SET snapshot_date = collected_at::date
 WHERE snapshot_date IS NULL;

ALTER TABLE apple_songs_performance
    ALTER COLUMN snapshot_date SET DEFAULT CURRENT_DATE;

ALTER TABLE apple_songs_performance
    ALTER COLUMN snapshot_date SET NOT NULL;

-- L'ancienne contrainte tombe, la nouvelle porte la date. `IF EXISTS` parce que le nom
-- généré par Postgres pour une contrainte inline est stable mais pas garanti par le
-- schéma d'origine.
ALTER TABLE apple_songs_performance
    DROP CONSTRAINT IF EXISTS apple_songs_performance_artist_id_song_name_key;

CREATE UNIQUE INDEX IF NOT EXISTS uq_apple_songs_perf_snapshot
    ON apple_songs_performance (artist_id, song_name, snapshot_date);

CREATE INDEX IF NOT EXISTS idx_apple_songs_perf_snapshot_date
    ON apple_songs_performance (artist_id, snapshot_date);
