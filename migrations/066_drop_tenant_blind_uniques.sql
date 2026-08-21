-- 066 — Supprimer les contraintes uniques aveugles au locataire (Meta placements).
--
-- ORDRE DE DÉPLOIEMENT : additive-safe, peut précéder le code.
-- Supprimer une contrainte n'a jamais cassé un écrivain — cela autorise seulement
-- plus de lignes. (Contraste avec 065, qui déplace une clé : voir sa bannière.)
--
-- Trouvé le 2026-08-20 par `make schema-check` une fois étendu aux CONTRAINTES
-- (il ne comparait que les colonnes, et déclarait « prod == canonique »).
--
-- `meta_insights_performance_placement` et `meta_insights_engagement_placement`
-- portent en production DEUX index uniques :
--
--   UNIQUE (campaign_name, platform, placement)              ← hérité, mono-tenant
--   UNIQUE (artist_id, campaign_name, platform, placement)   ← celui que le code cible
--
-- Le premier est un vestige d'avant le multi-tenant, absent du schéma canonique.
-- Il est nuisible et pas seulement inutile : **deux locataires ayant une campagne
-- du même nom sur la même plateforme et le même placement ne peuvent pas coexister**
-- — le second écrase le premier ou échoue. C'est la même classe que
-- `upsert-transfers-row-ownership`, exprimée dans le schéma plutôt que dans le code.
--
-- Le nom d'une contrainte générée par Postgres est tronqué à 63 caractères et
-- n'est pas stable d'une base à l'autre : on la retrouve donc par sa DÉFINITION,
-- jamais par son nom.

BEGIN;

DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT c.conrelid::regclass AS tbl, c.conname
        FROM pg_constraint c
        WHERE c.contype = 'u'
          AND c.connamespace = 'public'::regnamespace
          AND c.conrelid::regclass::text IN (
              'meta_insights_performance_placement',
              'meta_insights_engagement_placement')
          -- exactement les 3 colonnes héritées, sans artist_id
          AND pg_get_constraintdef(c.oid) = 'UNIQUE (campaign_name, platform, placement)'
    LOOP
        EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', r.tbl, r.conname);
        RAISE NOTICE 'dropped tenant-blind unique on %: %', r.tbl, r.conname;
    END LOOP;
END $$;

COMMIT;
