-- 096 — Rien d'écrasé n'est perdu : un journal des révisions, automatique.
--
-- Demandé le 2026-09-08 : « une solution automatique qui conserve les données
-- historiques si elles doivent être écrasées ».
--
-- LE RISQUE EST DOCUMENTÉ PAR LA SOURCE ELLE-MÊME. Spotify retire des streams
-- rétroactivement quand sa détection de fraude conclut — c'est écrit sur leur page
-- « Artificial Streaming » : les écoutes sont retirées, le taux de redevance de la
-- période est recalculé, et des royalties déjà versées sont reprises. Or notre upsert
-- écrase `(artist_id, song, date)` : un jour déjà collecté peut changer de valeur SANS
-- QUE RIEN NE LE VOIE. Personne ne peut aujourd'hui répondre à « ce chiffre a-t-il
-- changé depuis ? ».
--
-- POURQUOI UN DÉCLENCHEUR ET PAS DU PYTHON. `PostgresHandler.upsert_many` n'accepte que
-- des NOMS de colonnes dans `update_columns`, pas d'expressions : conserver l'ancienne
-- valeur demanderait de modifier le chemin d'écriture, et tout écrivain futur qui
-- l'oublie perdrait l'historique en silence. Un déclencheur ne s'oublie pas — il vaut
-- pour l'import CSV, pour un backfill, et pour le script qu'on n'a pas encore écrit.
-- Le dépôt a déjà ce patron : `trg_calculate_hypeddit_metrics` sur
-- `hypeddit_daily_stats`.
--
-- CE QU'IL NE FAIT PAS : il ne corrige rien. Une correction silencieuse est exactement
-- le défaut qu'on instrumente ici.

CREATE TABLE IF NOT EXISTS data_revisions (
    id          BIGSERIAL PRIMARY KEY,
    table_name  TEXT        NOT NULL,
    artist_id   INTEGER,                    -- lu sur la ligne quand elle en porte un
    row_key     JSONB       NOT NULL,       -- la clé métier de la ligne révisée
    column_name TEXT        NOT NULL,
    old_value   TEXT,
    new_value   TEXT,
    revised_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_data_revisions_when
    ON data_revisions (revised_at DESC);
CREATE INDEX IF NOT EXISTS idx_data_revisions_tenant
    ON data_revisions (artist_id, table_name, revised_at DESC);

COMMENT ON TABLE data_revisions IS
    'Journal append-only : une ligne par VALEUR écrasée. Alimenté par le déclencheur '
    'log_value_revision(), jamais par du code applicatif. Ne sert jamais de source de '
    'vérité — c''est une trace, pas un état.';

-- La fonction est GÉNÉRIQUE : elle lit la table dans `TG_TABLE_NAME` et reçoit DEUX
-- arguments — les colonnes surveillées, puis les colonnes de la clé métier, chacune
-- sous forme de liste séparée par des virgules. Inscrire une table coûte donc un seul
-- CREATE TRIGGER, et aucune ligne de Python.
--
-- Deux arguments et non un séparateur au milieu d'une liste : la première version
-- passait `('streams', '--', 'artist_id', …)` et découpait `TG_ARGV` autour du `--`.
-- Elle n'a JAMAIS rien journalisé, et la mesure l'a montrée avant livraison — `TG_ARGV`
-- est indexé À PARTIR DE 0 en PL/pgSQL alors qu'`array_position` rend un rang à partir
-- de 1, donc la boucle parcourait le séparateur au lieu de la colonne. Le découpage est
-- supprimé plutôt que corrigé : ce qu'on ne calcule pas ne peut pas être décalé.
CREATE OR REPLACE FUNCTION log_value_revision() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    watched  TEXT[] := string_to_array(TG_ARGV[0], ',');
    key_cols TEXT[] := string_to_array(TG_ARGV[1], ',');
    col      TEXT;
    old_v    TEXT;
    new_v    TEXT;
    key      JSONB := '{}'::JSONB;
    tenant   INTEGER := NULL;
BEGIN
    -- La clé métier, telle quelle : c'est elle qui permettra de relire la ligne.
    FOREACH col IN ARRAY key_cols LOOP
        key := key || jsonb_build_object(col, to_jsonb(NEW) -> col);
    END LOOP;

    IF (to_jsonb(NEW) ? 'artist_id') THEN
        tenant := (to_jsonb(NEW) ->> 'artist_id')::INTEGER;
    END IF;

    FOREACH col IN ARRAY watched LOOP
        old_v := to_jsonb(OLD) ->> col;
        new_v := to_jsonb(NEW) ->> col;
        -- `IS DISTINCT FROM` et non `<>` : deux NULL sont égaux ici, et une collecte
        -- qui réécrit la MÊME valeur ne doit produire aucune ligne. Sans ça le journal
        -- grossirait d'une ligne par titre et par nuit, pour ne rien dire.
        IF old_v IS DISTINCT FROM new_v THEN
            INSERT INTO data_revisions
                (table_name, artist_id, row_key, column_name, old_value, new_value)
            VALUES (TG_TABLE_NAME, tenant, key, col, old_v, new_v);
        END IF;
    END LOOP;

    RETURN NEW;
END;
$$;

-- Les tables inscrites : celles dont une écriture peut écraser une valeur DÉJÀ
-- collectée. Chacune nomme les colonnes qui portent une mesure, puis sa clé métier.
DROP TRIGGER IF EXISTS trg_revision_s4a_song_timeline ON s4a_song_timeline;
CREATE TRIGGER trg_revision_s4a_song_timeline
    BEFORE UPDATE ON s4a_song_timeline
    FOR EACH ROW EXECUTE FUNCTION
    log_value_revision('streams', 'artist_id,song,date');

DROP TRIGGER IF EXISTS trg_revision_apple_songs_performance ON apple_songs_performance;
CREATE TRIGGER trg_revision_apple_songs_performance
    BEFORE UPDATE ON apple_songs_performance
    FOR EACH ROW EXECUTE FUNCTION
    log_value_revision('plays,listeners,shazam_count',
                       'artist_id,song_name,snapshot_date,period_start,period_end');
