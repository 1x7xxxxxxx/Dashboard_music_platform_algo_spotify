-- ═══════════════════════════════════════════════════════════════════════════
-- 110 — Meta : le budget des campagnes ACTIVES, une seule fois
-- ═══════════════════════════════════════════════════════════════════════════
-- `SUM(lifetime_budget), SUM(daily_budget) FROM meta_campaigns WHERE status =
-- 'ACTIVE'` était recopié dans QUATRE branches de deux fichiers
-- (`trigger_algo/_common/_budget_roi.py`, `trigger_algo/_tab_budget_roi.py`),
-- chacune en deux versions — une par locataire, une pour la flotte.
--
-- La règle recopiée est `status = 'ACTIVE'`. Ce n'est pas une mesure collectée :
-- c'est une CONFIGURATION lue chez Meta, et elle alimente une tuile affichée
-- (« Budget Meta Ads »). Une tuile qui affiche un nombre a une définition, et une
-- définition recopiée quatre fois finit par diverger — il suffit qu'une seule
-- branche écrive `status IN ('ACTIVE','PAUSED')`.
--
-- Le `ad_account_id` est là parce que la page filtre dessus, et il n'y en a qu'un
-- dans cette vue : le défaut d'ambiguïté de la migration 108 n'est pas exprimable
-- ici.
CREATE OR REPLACE VIEW v_meta_active_budget AS
    SELECT artist_id,
           ad_account_id,
           campaign_id,
           campaign_name,
           COALESCE(lifetime_budget, 0)::numeric AS lifetime_budget,
           COALESCE(daily_budget, 0)::numeric    AS daily_budget
      FROM meta_campaigns
     WHERE artist_id IS NOT NULL
       AND status = 'ACTIVE';

COMMENT ON VIEW v_meta_active_budget IS
    'Couche OR (ADR-019) : le budget des campagnes Meta ACTIVES, par locataire. '
    'Porte le prédicat status = ''ACTIVE'', qui vivait recopié dans quatre '
    'branches de deux fichiers (migration 110).';
