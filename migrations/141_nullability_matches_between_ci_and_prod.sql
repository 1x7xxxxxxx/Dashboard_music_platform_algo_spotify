-- ═══════════════════════════════════════════════════════════════════════════
-- 141 — La nullabilité est la même en CI et en production (R219, 2026-09-27)
-- ═══════════════════════════════════════════════════════════════════════════
--
-- Mesuré le 2026-09-27 : le schéma canonique (init_db.sql + migrations, ce que la CI
-- provisionne) et la production diffèrent sur 13 colonnes — NOT NULL d'un côté,
-- NULLable de l'autre. Deux fixtures de test vertes en local (base = prod) sont
-- tombées rouges en CI. `make schema-check` ne le voyait pas : son empreinte ne
-- portait pas la nullabilité (corrigé dans le même lot, catégorie `nn:`).
--
-- DEUX SENS, parce que les deux côtés ont raison sur des colonnes différentes.
--
-- 1. La PRODUCTION rejoint le canonique sur 11 colonnes : aucune n'a jamais porté
--    de NULL (0 sur 22 à 16 236 lignes), les validateurs l'exigent déjà
--    (`meta_ads_validators` : `min_length=1` sur les trois noms Meta) et aucun
--    écrivain n'y met de NULL. Elles ont été créées NULLables par l'ancien schéma
--    des collecteurs, avant `init_db.sql`.
--    Le SET NOT NULL n'est posé QUE si la colonne n'a aucun NULL au moment où la
--    migration passe : sinon un NOTICE, et la colonne reste telle quelle — une
--    migration ne supprime ni n'invente une donnée pour passer.
--
-- 2. Le CANONIQUE rejoint la production sur 2 colonnes où NULL est LÉGITIME :
--    `saas_users.artist_id` (un compte admin sans artiste — 1 sur 8 en prod) et
--    `usage_events.artist_id` (un évènement anonyme — 223 sur 1 306). La migration
--    068 les rendait NOT NULL « là où les données le permettent » : sur la base VIDE
--    de la CI elle le pouvait, sur la prod non. Son résultat dépendait donc des
--    données présentes, et la CI refusait des états que la prod porte chaque jour.
--    068 exclut déjà `tracks` pour cette raison exacte ; ces deux-là y manquaient.
DO $$
DECLARE
    r record;
    has_nulls boolean;
BEGIN
    FOR r IN
        SELECT * FROM (VALUES
            ('apple_songs_history', 'date'),
            ('meta_ads', 'ad_name'),
            ('meta_adsets', 'adset_name'),
            ('meta_campaigns', 'campaign_name'),
            ('meta_insights_engagement_placement', 'placement'),
            ('meta_insights_engagement_placement', 'platform'),
            ('meta_insights_performance_placement', 'placement'),
            ('meta_insights_performance_placement', 'platform'),
            ('youtube_channel_history', 'channel_id'),
            ('youtube_video_stats', 'video_id'),
            ('youtube_videos', 'channel_id')
        ) AS v(table_name, column_name)
    LOOP
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns c
                        WHERE c.table_schema = 'public' AND c.table_name = r.table_name
                          AND c.column_name = r.column_name) THEN
            CONTINUE;
        END IF;
        EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I WHERE %I IS NULL)',
                       r.table_name, r.column_name) INTO has_nulls;
        IF has_nulls THEN
            RAISE NOTICE '141: %.% kept nullable — it holds NULL rows', r.table_name, r.column_name;
        ELSE
            EXECUTE format('ALTER TABLE %I ALTER COLUMN %I SET NOT NULL',
                           r.table_name, r.column_name);
        END IF;
    END LOOP;
END $$;

ALTER TABLE saas_users ALTER COLUMN artist_id DROP NOT NULL;
ALTER TABLE usage_events ALTER COLUMN artist_id DROP NOT NULL;
