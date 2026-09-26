-- ═══════════════════════════════════════════════════════════════════════════
-- 138 — Meta, maille publicité : clics sur le lien et clics sortants
-- ═══════════════════════════════════════════════════════════════════════════
-- Mesuré le 2026-09-26 sur spotify_etl_review, artiste 1 : la page Créatives
-- dessinait l'entonnoir « Impressions → Clics → Clics sortants » avec
--   * `clicks`      = « clics (tous) » de Meta (j'aime, agrandissements, profil) ;
--   * `conversions` = le résultat de l'objectif, qui comptait l'évènement sortant
--     d'Hypeddit DEUX FOIS (somme sur tous les action_type offsite_conversion.*),
--     et qui est une VUE VIDÉO sous THRUPLAY.
-- 18 des 61 couples (créative, campagne) avec dépense avaient conversions > clics :
-- l'entonnoir s'ÉLARGISSAIT (2 732 → 48 → 60 ; 2 028 → 7 → 1 670 sous THRUPLAY).
--
-- La maille campagne portait déjà `link_clicks` et `custom_conversions` ; la maille
-- publicité ne les avait pas. Elles entrent ici, NULLables : une ligne collectée
-- avant cette migration ne les a pas mesurées, et seule une re-collecte
-- `full_history` du DAG Meta les remplira.
--
-- `offsite_actions` garde, par publicité et par jour, les action_type
-- offsite_conversion.* que Meta a rendus avec leur valeur. Aucun payload brut
-- n'était conservé : c'est ce qui a empêché de SAVOIR quel second nom portait le
-- double compte. La règle de famille du collecteur devient ainsi vérifiable.
ALTER TABLE meta_insights ADD COLUMN IF NOT EXISTS link_clicks INTEGER;
ALTER TABLE meta_insights ADD COLUMN IF NOT EXISTS custom_conversions INTEGER;
ALTER TABLE meta_insights ADD COLUMN IF NOT EXISTS offsite_actions TEXT;

-- Même définition que la migration 108, colonnes neuves AJOUTÉES EN FIN DE LISTE :
-- `CREATE OR REPLACE VIEW` refuse de déplacer une colonne existante, et un
-- DROP VIEW casserait ce qui la lit.
CREATE OR REPLACE VIEW v_meta_creative_daily AS
    SELECT mi.artist_id,
           ma.ad_name                        AS creative_name,
           mc.campaign_name                  AS campaign_name,
           mi.date::date                     AS day,
           COALESCE(SUM(mi.spend), 0)::numeric       AS spend,
           COALESCE(SUM(mi.impressions), 0)::bigint  AS impressions,
           COALESCE(SUM(mi.clicks), 0)::bigint       AS clicks,
           COALESCE(SUM(mi.reach), 0)::bigint        AS reach,
           COALESCE(SUM(mi.conversions), 0)::bigint  AS conversions,
           AVG(mi.frequency)                         AS frequency,
           AVG(mi.ctr)                               AS ctr,
           ma.ad_account_id                          AS ad_account_id,
           ads.optimization_goal                     AS optimization_goal,
           -- Deux attributs, pas deux mesures : constants dans le groupe, ils sont
           -- là pour que le classement CPR de la page cesse de rejoindre
           -- `meta_campaigns` et `meta_ads` rien que pour les lire.
           MAX(mc.start_time)                        AS campaign_start,
           MAX(ma.created_time)                      AS creative_created,
           -- ⚠️ UNE MOYENNE NE SE RÉ-AGRÈGE PAS. `ctr` ci-dessus est la moyenne
           -- du JOUR ; en refaire la moyenne sur plusieurs jours ne donne pas la
           -- moyenne des lignes, parce qu'un nom de créative couvre plusieurs
           -- `ad_id` et que leur nombre varie d'un jour à l'autre — 274 couples
           -- (créative, jour) sont dans ce cas, mesurés le 2026-09-12.
           --
           -- La vue expose donc la SOMME et le COMPTE : le lecteur qui veut la
           -- moyenne sur une période fait `SUM(ctr_sum) / SUM(ctr_n)` et obtient
           -- exactement le nombre qu'une lecture des lignes brutes donnerait.
           -- C'est la seule façon de descendre ce grain sans déplacer un chiffre
           -- affiché.
           SUM(mi.ctr)                               AS ctr_sum,
           COUNT(mi.ctr)                             AS ctr_n,
           SUM(mi.frequency)                         AS frequency_sum,
           COUNT(mi.frequency)                       AS frequency_n,
           -- 138 : les deux étapes justes de l'entonnoir. SANS COALESCE, et c'est
           -- le point : une ligne collectée avant 138 n'a PAS mesuré ces étapes,
           -- elle ne les a pas mesurées à zéro. NULL se lit « non mesuré » ; un 0
           -- dessinerait un effondrement qui n'a pas eu lieu.
           SUM(mi.link_clicks)::bigint               AS link_clicks,
           SUM(mi.custom_conversions)::bigint        AS custom_conversions,
           COUNT(mi.custom_conversions)              AS measured_n,
           COUNT(*)                                  AS rows_n
      FROM meta_insights mi
      JOIN meta_ads ma ON ma.ad_id = mi.ad_id AND ma.artist_id = mi.artist_id
      -- LEFT : une créative dont la campagne a disparu du catalogue Meta reste une
      -- créative, et ses dépenses restent dépensées. Un INNER la ferait disparaître
      -- du total sans rien dire — la forme de défaut que ce dépôt paie le plus cher.
      LEFT JOIN meta_campaigns mc ON mc.campaign_id = ma.campaign_id
                                 AND mc.artist_id = ma.artist_id
      LEFT JOIN meta_adsets ads ON ads.adset_id = ma.adset_id
                               AND ads.artist_id = ma.artist_id
     WHERE mi.artist_id IS NOT NULL
     GROUP BY mi.artist_id, ma.ad_account_id, ma.ad_name, mc.campaign_name,
              ads.optimization_goal, mi.date::date;

COMMENT ON COLUMN meta_insights.link_clicks IS
    'inline_link_clicks de Meta (clics sur le lien). NULL = collecté avant la migration 138.';
COMMENT ON COLUMN meta_insights.custom_conversions IS
    'Clics sortants Hypeddit (famille offsite_conversion.custom*). NULL = collecté avant 138.';
COMMENT ON COLUMN meta_insights.offsite_actions IS
    'action_type offsite_conversion.* rendus par Meta, « type=valeur;… » — pour auditer la règle de famille des résultats.';
