-- 076 — `ad_account_id` sur les tables Meta à la maille CAMPAGNE.
--
-- Pourquoi, et pourquoi le schéma AVANT l'interface (R53, 2026-08-23) :
--
-- Un artiste passant par une agence a plusieurs comptes publicitaires. Aujourd'hui le
-- formulaire n'accepte qu'un `account_id`, et les dix tables d'insights à la maille
-- campagne sont uniques sur `campaign_name` SANS discriminant de compte. Deux
-- conséquences, la seconde bien pire que la première :
--
--   1. deux comptes ayant une campagne du même nom — « Release FR », le cas le plus
--      banal chez une agence — écrivent la MÊME ligne et s'écrasent l'un l'autre ;
--
--   2. `_prune_renamed_campaigns` exécute
--          DELETE FROM <table> WHERE artist_id = %s AND campaign_name <> ALL(%s)
--      En boucle sur deux comptes, la passe du second EFFACE tout ce que le premier
--      vient d'écrire. Ce n'est pas une collision, c'est une suppression de masse.
--
-- Livrer l'interface multi-comptes avant cette migration produirait donc des données
-- silencieusement fausses. D'où l'ordre : schéma, puis collecteur, puis interface.
--
-- La migration est ADDITIVE et rétro-compatible :
--   * la colonne est nullable et vaut NULL pour tout l'existant ;
--   * les contraintes d'unicité actuelles ne sont PAS supprimées ici — les remplacer
--     exige que le collecteur remplisse déjà la colonne, sinon le premier upsert
--     mono-compte violerait la nouvelle clé. Elles le seront dans la migration qui
--     accompagnera la boucle collecteur.
--
-- Idempotente : rejouable sans effet.

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
        -- provenance : savoir de quel compte vient une campagne, un adset, une pub
        'meta_campaigns', 'meta_adsets', 'meta_ads'
    ]
    LOOP
        IF EXISTS (SELECT 1 FROM information_schema.tables
                   WHERE table_schema = 'public' AND table_name = tbl) THEN
            EXECUTE format(
                'ALTER TABLE %I ADD COLUMN IF NOT EXISTS ad_account_id VARCHAR(32)', tbl);
            -- Index partiel : tant que la flotte est mono-compte la colonne est NULL
            -- partout, et un index plein ne coûterait que de l'espace.
            EXECUTE format(
                'CREATE INDEX IF NOT EXISTS idx_%s_ad_account ON %I (artist_id, ad_account_id) '
                'WHERE ad_account_id IS NOT NULL', tbl, tbl);
        END IF;
    END LOOP;
END $$;

COMMENT ON COLUMN meta_campaigns.ad_account_id IS
    'Compte publicitaire Meta (act_…) dont vient cette campagne. NULL = collecté avant '
    'le multi-comptes (R53). Devient obligatoire quand la boucle collecteur multi-comptes '
    'est livrée.';
