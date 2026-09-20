-- Deux identifiants de plateforme redeviennent du TEXTE — 2026-09-20 (R135)
--
-- Ce que cette migration corrige
-- ------------------------------
-- Deux colonnes portent en base un type différent de celui que le dépôt déclare, et les
-- deux sont des IDENTIFIANTS venus d'une API externe :
--
--   * `soundcloud_tracks_daily.track_id` — `bigint` en PRODUCTION, `character varying`
--     en local. `init_db.sql:106` le déclare `VARCHAR(50) NOT NULL` depuis toujours, et
--     `soundcloud_api_collector.py:222` écrit `str(track.get('id'))`.
--   * `instagram_daily_stats.ig_user_id` — `bigint` en LOCAL, déclaré `VARCHAR`. C'est
--     une IDENTITÉ DE LOCATAIRE, lue `17841402151518986` : au-delà de 2^53, donc un
--     nombre que tout passage par JSON ou JavaScript arrondirait en silence.
--
-- Pourquoi le canonique est le TEXTE, et pas l'entier
-- ---------------------------------------------------
-- Ce ne sont pas des nombres. On ne les additionne pas, on ne les ordonne pas, on ne les
-- soustrait pas : on les compare et on les transmet. SoundCloud et Meta les documentent
-- comme des chaînes opaques, et rien ne garantit qu'ils resteront numériques — Meta a
-- déjà livré des identifiants alphanumériques sur d'autres objets. Un `bigint` est donc
-- une affirmation sur un format que nous ne contrôlons pas.
--
-- ⚠️ CONSÉQUENCE AUJOURD'HUI : AUCUNE, et c'est pour cela que cette divergence a vécu
-- des mois. Rien ne compare ces colonnes à une chaîne ; Postgres transtype les deux sens
-- à l'écriture. Elle apparaîtra au premier `WHERE col = %s` avec un paramètre texte, ou
-- à la première jointure entre les deux environnements :
--     ERROR: operator does not exist: bigint = text
-- Autrement dit, un test vert ici échouera là-bas. C'est une divergence dev↔prod, pas un
-- bogue visible, et c'est la forme la plus coûteuse à découvrir tard.
--
-- La cause racine, qui dépasse ces deux colonnes
-- ----------------------------------------------
-- `init_db.sql` emploie `CREATE TABLE IF NOT EXISTS` **55 fois**. Sur une base où la
-- table existe déjà, la déclaration n'est PAS appliquée : elle est ignorée, sans un mot.
-- Une colonne ajoutée à ce fichier ne change donc aucune base déjà créée. Classe
-- `a-create-if-not-exists-that-declares-nothing` ; garde
-- `tests/test_the_declared_schema_matches_the_database.py` ; rapport `make schema-declared`.
--
-- Pourquoi les vues sont capturées au lieu d'être recopiées
-- ---------------------------------------------------------
-- `v_platform_levels` et `v_soundcloud_track_latest` dépendent de `track_id`, et
-- PostgreSQL refuse `ALTER COLUMN … TYPE` tant qu'une vue lit la colonne. Elles font
-- ~110 lignes de SQL à elles deux. Les recopier ici serait créer une seconde définition
-- qui doit coïncider avec la première — exactement la classe
-- `two-definitions-that-must-coincide-are-never-compared`, et la prochaine migration de
-- ces vues laisserait cette copie derrière elle.
-- Elles sont donc LUES dans le catalogue (`pg_get_viewdef`), déposées, puis recréées
-- telles quelles.
--
-- ⚠️ **LA CAPTURE EST TRANSITIVE, et la première version ne l'était pas.** Elle ne
-- cherchait que les vues dépendant DIRECTEMENT de la colonne — elle en trouvait deux — et
-- déposait avec `CASCADE`. Or `v_platform_totals` lit `v_soundcloud_track_latest` : le
-- `CASCADE` l'emportait, et rien ne la recréait. Mesuré le 2026-09-20 en jouant la
-- migration sur l'état de la production reproduit en local : **23 tests rouges**, dont
-- l'invariant de la couche or, et une vue de production manquante. Sur la prod, cette
-- version aurait supprimé une vue en silence.
--
-- Le `CASCADE` et une capture directe sont donc incompatibles par construction : l'un
-- agit transitivement, l'autre regarde un seul niveau. La requête ci-dessous calcule la
-- FERMETURE par un CTE récursif, note la profondeur de chaque vue, dépose des feuilles
-- vers la racine et recrée dans l'ordre inverse.
--
-- Idempotente : chaque bloc ne fait rien si la colonne porte déjà le bon type.
-- Longueurs mesurées le 2026-09-20 : `track_id` 10 caractères au plus,
-- `ig_user_id` 17. VARCHAR(50) laisse trois fois la marge observée.

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. soundcloud_tracks_daily.track_id → VARCHAR(50)
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
    v_type   text;
    v_rec    record;
    v_defs   text[] := ARRAY[]::text[];
    v_noms   text[] := ARRAY[]::text[];
    i        int;
BEGIN
    SELECT data_type INTO v_type
      FROM information_schema.columns
     WHERE table_schema = 'public'
       AND table_name  = 'soundcloud_tracks_daily'
       AND column_name = 'track_id';

    IF v_type IS NULL THEN
        RAISE NOTICE 'soundcloud_tracks_daily.track_id absente — rien à faire';
        RETURN;
    END IF;
    IF v_type = 'character varying' THEN
        RAISE NOTICE 'soundcloud_tracks_daily.track_id est déjà character varying';
        RETURN;
    END IF;

    RAISE NOTICE 'soundcloud_tracks_daily.track_id est % — conversion en VARCHAR(50)', v_type;

    -- Capturer la FERMETURE TRANSITIVE des vues, dans le catalogue et non à la main :
    -- celles qui lisent la colonne, PUIS celles qui lisent ces vues, et ainsi de suite.
    -- `profondeur` croissante = plus loin de la table ; on dépose du plus loin vers le
    -- plus près, et on recrée dans l'ordre inverse.
    FOR v_rec IN
        WITH RECURSIVE ferme AS (
            -- niveau 1 : les vues qui lisent DIRECTEMENT `track_id`
            SELECT DISTINCT dep.oid, 1 AS profondeur
              FROM pg_depend d
              JOIN pg_rewrite rw ON rw.oid = d.objid
              JOIN pg_class dep  ON dep.oid = rw.ev_class
              JOIN pg_class src  ON src.oid = d.refobjid
              JOIN pg_attribute a ON a.attrelid = src.oid AND a.attnum = d.refobjsubid
             WHERE src.relname = 'soundcloud_tracks_daily'
               AND a.attname   = 'track_id'
               AND dep.relkind = 'v'
            UNION
            -- niveaux suivants : les vues qui lisent une vue déjà retenue
            SELECT DISTINCT dep.oid, f.profondeur + 1
              FROM ferme f
              JOIN pg_depend d   ON d.refobjid = f.oid
              JOIN pg_rewrite rw ON rw.oid = d.objid
              JOIN pg_class dep  ON dep.oid = rw.ev_class
             WHERE dep.relkind = 'v'
               AND dep.oid <> f.oid
               AND f.profondeur < 10          -- borne : une hiérarchie de vues cyclique
                                              -- est impossible, mais une borne rend la
                                              -- migration incapable de boucler
        )
        SELECT c.relname AS nom,
               pg_get_viewdef(c.oid, true) AS def,
               max(f.profondeur) AS profondeur
          FROM ferme f
          JOIN pg_class c ON c.oid = f.oid
         GROUP BY c.relname, c.oid
         ORDER BY max(f.profondeur) DESC      -- des feuilles vers la racine
    LOOP
        v_noms := array_append(v_noms, v_rec.nom);
        v_defs := array_append(v_defs, v_rec.def);
        RAISE NOTICE '  vue capturée : % (profondeur %)', v_rec.nom, v_rec.profondeur;
    END LOOP;

    FOR i IN 1 .. coalesce(array_length(v_noms, 1), 0) LOOP
        EXECUTE format('DROP VIEW IF EXISTS %I CASCADE', v_noms[i]);
        RAISE NOTICE '  vue déposée : %', v_noms[i];
    END LOOP;

    ALTER TABLE soundcloud_tracks_daily
        ALTER COLUMN track_id TYPE VARCHAR(50) USING track_id::text;

    -- Ordre INVERSE de la dépose : une vue ne peut être créée qu'après celles qu'elle lit.
    FOR i IN REVERSE coalesce(array_length(v_noms, 1), 0) .. 1 LOOP
        EXECUTE format('CREATE OR REPLACE VIEW %I AS %s', v_noms[i], v_defs[i]);
        RAISE NOTICE '  vue recréée : %', v_noms[i];
    END LOOP;
END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. instagram_daily_stats.ig_user_id → VARCHAR(50)
-- ─────────────────────────────────────────────────────────────────────────────
-- Aucune vue ne dépend de cette colonne (vérifié le 2026-09-20). L'index unique
-- `instagram_daily_stats_artist_id_ig_user_id_day_key` est reconstruit automatiquement
-- par PostgreSQL à la conversion.
DO $$
DECLARE
    v_type text;
BEGIN
    SELECT data_type INTO v_type
      FROM information_schema.columns
     WHERE table_schema = 'public'
       AND table_name  = 'instagram_daily_stats'
       AND column_name = 'ig_user_id';

    IF v_type IS NULL THEN
        RAISE NOTICE 'instagram_daily_stats.ig_user_id absente — rien à faire';
        RETURN;
    END IF;
    IF v_type = 'character varying' THEN
        RAISE NOTICE 'instagram_daily_stats.ig_user_id est déjà character varying';
        RETURN;
    END IF;

    RAISE NOTICE 'instagram_daily_stats.ig_user_id est % — conversion en VARCHAR(50)', v_type;
    ALTER TABLE instagram_daily_stats
        ALTER COLUMN ig_user_id TYPE VARCHAR(50) USING ig_user_id::text;
END $$;
