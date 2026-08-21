-- 067 — Rétablir en production les 3 clés étrangères Meta que le canonique déclare.
--
-- ORDRE DE DÉPLOIEMENT : indépendant du code. C'est une contrainte RESTRICTIVE,
-- donc elle mérite la vérification faite avant écriture, pas après :
--   * orphelins mesurés en production le 2026-08-20 : 0 / 0 / 0 (sur 144 ads,
--     69 adsets, 34 campagnes) — la validation passe donc sans rien rejeter ;
--   * l'ordre d'insertion du collecteur respecte déjà la hiérarchie
--     (`_meta_upsert.py` : campaigns → adsets → ads) ;
--   * le schéma canonique — donc la CI — porte ces clés depuis toujours : c'est la
--     production qui a dérivé, et le code est déjà testé avec elles.
--
-- Sans ces clés, la production accepte des adsets rattachés à une campagne
-- inexistante ; les vues Meta joignent alors sur du vide et affichent des trous
-- sans que rien ne le signale.
--
-- Dérive trouvée par `make schema-check` le 2026-08-20, le jour où il a été étendu
-- aux contraintes : la comparaison colonne-à-colonne le déclarait « prod ==
-- canonique » depuis des mois.
--
-- Idempotent : chaque clé n'est ajoutée que si aucune contrainte de même
-- définition n'existe déjà (les noms générés ne sont pas comparables).

BEGIN;

DO $$
DECLARE
    want RECORD;
BEGIN
    FOR want IN
        SELECT * FROM (VALUES
            ('meta_adsets', 'campaign_id', 'meta_campaigns', 'campaign_id'),
            ('meta_ads',    'campaign_id', 'meta_campaigns', 'campaign_id'),
            ('meta_ads',    'adset_id',    'meta_adsets',    'adset_id')
        ) AS t(child, child_col, parent, parent_col)
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE contype = 'f'
              AND conrelid = want.child::regclass
              AND pg_get_constraintdef(oid) = format(
                    'FOREIGN KEY (%s) REFERENCES %s(%s)',
                    want.child_col, want.parent, want.parent_col)
        ) THEN
            EXECUTE format(
                'ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES %I(%I)',
                want.child, want.child || '_' || want.child_col || '_fkey',
                want.child_col, want.parent, want.parent_col);
            RAISE NOTICE 'added FK %.% -> %.%',
                want.child, want.child_col, want.parent, want.parent_col;
        END IF;
    END LOOP;
END $$;

COMMIT;
