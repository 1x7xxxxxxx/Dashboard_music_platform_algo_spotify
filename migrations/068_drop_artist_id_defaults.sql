-- 068 — `artist_id` n'a plus de valeur par défaut.
--
-- ⚠️  ORDRE DE DÉPLOIEMENT — CETTE MIGRATION N'EST PAS AUTONOME
--
-- Elle rend FATALE une écriture qui omet son locataire. C'est précisément le but,
-- et c'est pour cela qu'elle doit être appliquée **après** le déploiement du code
-- qui nomme toujours l'`artist_id` : le code encore en production omet la colonne
-- sur `track_popularity_history`, et cette migration transformerait son silence en
-- échec du DAG Spotify.
--
--   Séquence :  déployer le code  →  `python3 .claude/scripts/audit_tenant_writes.py`
--               (doit rendre « 0 missing »)  →  puis `make migrate`.
--
-- Voir la classe `migration-ahead-of-its-code` : le 2026-08-20, la migration 065
-- appliquée avant son code a cassé la collecte YouTube en quelques minutes.
--
-- ── Pourquoi ────────────────────────────────────────────────────────────────
--
-- `artist_id INTEGER DEFAULT 1` est un vestige du temps où il n'y avait qu'un
-- locataire. Depuis, il transforme « le développeur a oublié le locataire » en
-- « l'admin est propriétaire », sans erreur, sans alerte et sans trace.
--
-- Effet réel mesuré : `track_popularity_history` a stocké l'historique de
-- popularité Spotify de TOUS les locataires sous `artist_id = 1` pendant des mois.
-- Le payload n'avait pas la clé, `upsert_many` dérive les colonnes de l'INSERT des
-- clés du payload, Postgres a rempli le reste. Classe
-- `write-without-explicit-artist-id`.
--
-- Le garde côté code (`audit_tenant_writes.py`) attrape désormais l'oubli à
-- l'écriture. Celui-ci le rend impossible à ignorer côté base : les deux filets
-- doivent exister, parce que le premier ne voit que ce qu'il sait résoudre.
--
-- ── DEFAULT retiré ET NOT NULL posé, quand c'est possible ───────────────────
--
-- Retirer le seul DEFAULT ne suffit pas : l'écriture fautive passe alors en
-- `artist_id = NULL`. C'est déjà mieux — une ligne NULL n'apparaît sous personne,
-- au lieu d'apparaître sous l'admin — mais c'est encore silencieux. `NOT NULL` est
-- ce qui rend l'oubli *fatal*, donc visible.
--
-- La contrainte n'est posée que sur les colonnes qui ne contiennent AUCUN NULL
-- aujourd'hui ; celles qui en contiennent sont listées en NOTICE et laissées en
-- l'état plutôt que de faire échouer la migration. On préfère un rapport à un
-- blocage : les lignes historiques sans propriétaire sont un nettoyage
-- (`tools/tenant_contamination_check.py`), pas un obstacle à la règle.
--
-- Idempotent : ne touche que ce qui n'est pas déjà dans l'état voulu.

-- ── Piège : `artist_id` ne désigne pas toujours le locataire ────────────────
--
-- Trois tables héritées du monde mono-tenant utilisent `artist_id` comme
-- identifiant **Spotify** (VARCHAR) : `artists`, `artist_history`, `tracks`.
-- Le locataire y est `saas_artist_id` (INTEGER), quand il existe. Une première
-- version de cette migration raisonnait sur le NOM de la colonne et a posé
-- NOT NULL sur `tracks.artist_id` — la suite de tests l'a montré immédiatement.
-- On filtre donc sur le TYPE : seule une colonne INTEGER est un locataire.

BEGIN;

DO $$
DECLARE
    r RECORD;
    n INT := 0;
    has_nulls BOOLEAN;
BEGIN
    FOR r IN
        SELECT c.table_name, c.column_name
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON t.table_schema = c.table_schema AND t.table_name = c.table_name
        WHERE c.table_schema = 'public'
          AND t.table_type = 'BASE TABLE'
          AND c.column_name IN ('artist_id', 'saas_artist_id')
          AND c.data_type = 'integer'          -- cf. la note ci-dessus
          AND c.column_default IS NOT NULL
        ORDER BY 1
    LOOP
        EXECUTE format('ALTER TABLE %I ALTER COLUMN %I DROP DEFAULT',
                       r.table_name, r.column_name);
        n := n + 1;
    END LOOP;
    RAISE NOTICE '068: dropped the tenant-column DEFAULT on % column(s)', n;

    -- NOT NULL where the data already allows it.
    n := 0;
    FOR r IN
        SELECT c.table_name, c.column_name
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON t.table_schema = c.table_schema AND t.table_name = c.table_name
        WHERE c.table_schema = 'public'
          AND t.table_type = 'BASE TABLE'
          AND c.column_name IN ('artist_id', 'saas_artist_id')
          AND c.data_type = 'integer'          -- cf. la note ci-dessus
          AND c.is_nullable = 'YES'
          -- `tracks` est un CATALOGUE, pas une table de faits par locataire : une
          -- piste Spotify qu'aucun locataire ne revendique y existe légitimement
          -- avec saas_artist_id NULL, et spotify_api_daily écrit ce NULL
          -- volontairement plutôt que d'inventer un propriétaire — exactement la
          -- règle que cette migration défend. La rendre NOT NULL casserait la
          -- collecte. Exclusion explicite, pas oubli.
          AND NOT (c.table_name = 'tracks' AND c.column_name = 'saas_artist_id')
        ORDER BY 1
    LOOP
        EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I WHERE %I IS NULL)',
                       r.table_name, r.column_name) INTO has_nulls;
        IF has_nulls THEN
            RAISE NOTICE '068: % .% kept nullable — existing NULL rows (clean up '
                         'with tools/tenant_contamination_check.py, then re-run)',
                         r.table_name, r.column_name;
        ELSE
            EXECUTE format('ALTER TABLE %I ALTER COLUMN %I SET NOT NULL',
                           r.table_name, r.column_name);
            n := n + 1;
        END IF;
    END LOOP;
    RAISE NOTICE '068: set NOT NULL on % tenant column(s)', n;
END $$;

COMMIT;
