-- ═══════════════════════════════════════════════════════════════════════════
-- 138 — Meta : deux jointures qui multipliaient la maille
-- ═══════════════════════════════════════════════════════════════════════════
-- ⚠️ DÉFAUT VIVANT, mesuré le 2026-09-26 sur `spotify_etl_review`.
--
-- 1. L'ENGAGEMENT n'avait pas de vue or. `meta_insights_engagement` porte les
--    DEUX générations de lignes que la migration 109 a décrites pour la
--    performance : 231 lignes quotidiennes, chacune avec sa jumelle dans
--    `meta_insights_engagement_day`, et 21 lignes de cumul à vie (2025-12-15)
--    sans jumelle. Sommées ensemble, les tuiles de `meta_ads_overview`
--    affichaient exactement le double pour l'artiste 1 :
--
--        saves 1 094 (vrai 547) · shares 16 (vrai 8) · interactions 957 320
--        (vrai 478 968)
--
--    Et lue SANS `GROUP BY`, la table (une ligne par campagne ET par jour)
--    était fusionnée sur `campaign_name` seul avec un cadre d'une ligne par
--    campagne : 21 campagnes devenaient 252 lignes, et « les 12 plus
--    dépensières » dessinaient 12 copies de LA MÊME campagne (12 × 755,52 €).
--    Le tableau récapitulatif joignait la même table jour × jour sous un
--    `SUM(p.spend)` : 24 176,64 € pour une campagne de 755,52 € (× 32).
--
--    La règle est celle de 109, mot pour mot : une ligne quotidienne a sa
--    jumelle dans `_day`, écrite dans la même itération du collecteur ; une
--    ligne de cumul n'en a pas. Mesuré : 231 jumelles, 0 valeur divergente.
--    Le compte publicitaire entre dans la jumelle (IS NOT DISTINCT FROM) : un
--    locataire multi-comptes peut porter deux campagnes du même nom le même
--    jour, et chacune doit trouver SA jumelle.
--
-- 2. L'onglet « Réglages » (trigger_algo/_tab_reglages.py) joignait
--    `meta_ads × meta_insights` sur `ad_id` seul. Le bac à sable (locataire 18)
--    porte des copies des `ad_id` du locataire 1 : les dépenses des deux
--    s'additionnaient — 6 168,70 € = 3 087,82 + 3 080,88. C'est la classe que
--    106 et 108 ont fermée pour les créatives, recopiée une fois de plus parce
--    que `call_to_action`, `title` et `objective` n'étaient portées par aucune
--    vue. `v_meta_ad_daily` les porte, avec le locataire nommé à CHAQUE
--    jointure.
CREATE OR REPLACE VIEW v_meta_engagement_daily AS
    SELECT e.artist_id,
           e.ad_account_id,
           e.campaign_name,
           e.date_start                               AS day,
           COALESCE(e.page_interactions, 0)::bigint   AS page_interactions,
           COALESCE(e.post_reactions, 0)::bigint      AS post_reactions,
           COALESCE(e.comments, 0)::bigint            AS comments,
           COALESCE(e.saves, 0)::bigint               AS saves,
           COALESCE(e.shares, 0)::bigint              AS shares,
           COALESCE(e.link_clicks, 0)::bigint         AS link_clicks,
           COALESCE(e.post_likes, 0)::bigint          AS post_likes,
           e.collected_at
      FROM meta_insights_engagement e
     WHERE e.artist_id IS NOT NULL
       AND EXISTS (
           SELECT 1 FROM meta_insights_engagement_day d
            WHERE d.artist_id     = e.artist_id
              AND d.campaign_name = e.campaign_name
              AND d.day_date      = e.date_start
              AND d.ad_account_id IS NOT DISTINCT FROM e.ad_account_id);

COMMENT ON VIEW v_meta_engagement_daily IS
    'Couche OR (ADR-019) : l''engagement Meta au grain (locataire, compte, '
    'campagne, jour). Écarte les lignes de cumul à vie (même règle que '
    'v_meta_campaign_daily, migration 109) — elles faisaient afficher le double '
    '(migration 138). Un lecteur par campagne fait GROUP BY campaign_name.';

CREATE OR REPLACE VIEW v_meta_ad_daily AS
    SELECT mi.artist_id,
           ma.ad_account_id,
           mi.ad_id,
           mi.date::date                              AS day,
           ma.call_to_action,
           ma.title,
           mc.objective,
           mc.campaign_name,
           COALESCE(SUM(mi.spend), 0)::numeric        AS spend,
           COALESCE(SUM(mi.clicks), 0)::bigint        AS clicks,
           COALESCE(SUM(mi.impressions), 0)::bigint   AS impressions
      FROM meta_insights mi
      JOIN meta_ads ma ON ma.ad_id = mi.ad_id AND ma.artist_id = mi.artist_id
      -- LEFT, comme v_meta_creative_daily : une annonce dont la campagne a quitté
      -- le catalogue reste une dépense.
      LEFT JOIN meta_campaigns mc ON mc.campaign_id = ma.campaign_id
                                 AND mc.artist_id = ma.artist_id
     WHERE mi.artist_id IS NOT NULL
     GROUP BY mi.artist_id, ma.ad_account_id, mi.ad_id, mi.date::date,
              ma.call_to_action, ma.title, mc.objective, mc.campaign_name;

COMMENT ON VIEW v_meta_ad_daily IS
    'Couche OR (ADR-019) : la performance Meta au grain (locataire, annonce, '
    'jour), avec les réglages de l''annonce (call_to_action, title) et de sa '
    'campagne (objective). Le locataire est nommé à chaque jointure : l''onglet '
    'Réglages additionnait deux locataires qui partageaient un ad_id (migration 138).';
