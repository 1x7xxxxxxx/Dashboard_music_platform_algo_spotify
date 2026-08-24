-- 077 — `ad_account_id` entre dans la CLÉ D'UNICITÉ des tables Meta à la maille
-- campagne, et l'historique est rattaché au compte dont il vient.
--
-- Suite directe de 076 (R53 / ADR-013 « Meta multi-comptes, forme séparée »).
--
-- 076 a ajouté la colonne, délibérément SANS toucher aux contraintes : les
-- remplacer exigeait que le collecteur remplisse déjà la colonne, sinon le premier
-- upsert mono-compte violait la nouvelle clé. Le collecteur la remplit désormais
-- (`_MetaUpsertMixin._tag_account`), donc l'ordre est respecté : schéma → collecteur
-- → clés → interface.
--
-- Ce que cette migration ferme concrètement : deux comptes publicitaires d'une même
-- agence ayant tous deux une campagne « Release FR » — le nom le plus banal qui soit
-- — écrivaient LA MÊME LIGNE. Le second écrasait le premier, et le total de dépense
-- affiché était celui d'un seul des deux comptes, sans que rien ne le signale.
--
-- Deux points de conception, tous deux à contre-courant du réflexe :
--
--   1. `NULLS NOT DISTINCT` (PostgreSQL 15+, la prod est en 17). Par défaut Postgres
--      considère deux NULL comme DIFFÉRENTS dans un index unique : une clé
--      incluant `ad_account_id` aurait donc cessé de dédupliquer toute ligne
--      historique restée à NULL, et chaque nuit y aurait AJOUTÉ un doublon au lieu
--      de mettre à jour. La contrainte serait passée « verte » en produisant
--      exactement le défaut qu'elle est censée empêcher.
--
--   2. Le backfill n'est fait QUE pour les locataires déclarant EXACTEMENT UN
--      compte. Rattacher l'historique au compte courant n'est correct que tant que
--      ce compte est le seul qui ait jamais collecté — ce qui est vrai de toute la
--      flotte aujourd'hui, et cesse de l'être dès la première agence branchée.
--      C'est donc le dernier moment où ce rattachement est vrai ; le faire plus tard
--      serait deviner. Un locataire déjà multi-comptes garde ses NULL, que
--      `NULLS NOT DISTINCT` traite exactement comme avant la migration.
--
-- Idempotente : rejouable sans effet.

-- ── 1. Backfill : l'historique porte le compte dont il vient ──────────────────
DO $$
DECLARE
    tbl text;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'meta_insights_performance', 'meta_insights_performance_day',
        'meta_insights_performance_age', 'meta_insights_performance_country',
        'meta_insights_performance_placement',
        'meta_insights_engagement', 'meta_insights_engagement_day',
        'meta_insights_engagement_age', 'meta_insights_engagement_country',
        'meta_insights_engagement_placement',
        'meta_campaigns', 'meta_adsets', 'meta_ads'
    ]
    LOOP
        IF EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = tbl
                     AND column_name = 'ad_account_id') THEN
            EXECUTE format($f$
                UPDATE %I t
                SET ad_account_id = sub.acct
                FROM (
                    SELECT c.artist_id,
                           CASE WHEN c.extra_config->>'account_id' LIKE 'act!_%%' ESCAPE '!'
                                THEN c.extra_config->>'account_id'
                                ELSE 'act_' || (c.extra_config->>'account_id')
                           END AS acct
                    FROM artist_credentials c
                    WHERE c.platform = 'meta'
                      AND COALESCE(c.extra_config->>'account_id', '') <> ''
                      -- Exactement un compte déclaré : voir le point 2 ci-dessus.
                      AND COALESCE(
                            jsonb_array_length(
                                CASE WHEN jsonb_typeof(c.extra_config->'account_ids') = 'array'
                                     THEN c.extra_config->'account_ids' END),
                            1) = 1
                ) sub
                WHERE t.artist_id = sub.artist_id
                  AND t.ad_account_id IS NULL
            $f$, tbl);
        END IF;
    END LOOP;
END $$;

-- ── 2. Les clés d'unicité incluent le compte ─────────────────────────────────
-- Les noms de contraintes générés par Postgres sont TRONQUÉS à 63 caractères
-- (`meta_insights_engagement_age_artist_id_campaign_name_age_range_`), donc ils ne
-- sont pas retapés ici : on lit la contrainte unique existante dans le catalogue.
-- Une liste de dix noms tapée à la main, c'est une migration qui échoue sur la
-- première troncature qu'on a mal recopiée.
DO $$
DECLARE
    spec  record;
    con   record;
    cols  text;
BEGIN
    FOR spec IN
        SELECT * FROM (VALUES
            ('meta_insights_performance',           'campaign_name, date_start'),
            ('meta_insights_performance_day',       'campaign_name, day_date'),
            ('meta_insights_performance_age',       'campaign_name, age_range'),
            ('meta_insights_performance_country',   'campaign_name, country'),
            ('meta_insights_performance_placement', 'campaign_name, platform, placement'),
            ('meta_insights_engagement',            'campaign_name, date_start'),
            ('meta_insights_engagement_day',        'campaign_name, day_date'),
            ('meta_insights_engagement_age',        'campaign_name, age_range'),
            ('meta_insights_engagement_country',    'campaign_name, country'),
            ('meta_insights_engagement_placement',  'campaign_name, platform, placement')
        ) AS v(tbl, rest)
    LOOP
        CONTINUE WHEN NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = spec.tbl);

        cols := format('artist_id, ad_account_id, %s', spec.rest);

        -- Déjà passée ? La nouvelle contrainte porte un nom explicite.
        CONTINUE WHEN EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = spec.tbl || '_uniq_acct' AND contype = 'u');

        -- L'ancienne : la seule contrainte UNIQUE de la table qui ne soit pas la PK.
        FOR con IN
            SELECT conname FROM pg_constraint
            WHERE conrelid = format('public.%I', spec.tbl)::regclass
              AND contype = 'u'
        LOOP
            EXECUTE format('ALTER TABLE %I DROP CONSTRAINT %I', spec.tbl, con.conname);
        END LOOP;

        EXECUTE format(
            'ALTER TABLE %I ADD CONSTRAINT %I UNIQUE NULLS NOT DISTINCT (%s)',
            spec.tbl, spec.tbl || '_uniq_acct', cols);
    END LOOP;
END $$;

COMMENT ON COLUMN meta_campaigns.ad_account_id IS
    'Compte publicitaire Meta (act_…) dont vient cette campagne. Rempli par le '
    'collecteur à chaque tour de la boucle multi-comptes (R53). NULL = locataire '
    'sans credentials Meta au moment de la migration 077.';
