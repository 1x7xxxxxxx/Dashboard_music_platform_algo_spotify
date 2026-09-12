-- 106 — Les quatre dernières mailles entrent dans la couche OR (R94, fin).
--
-- Après Spotify (105), Apple (102/103) et la dépense Meta (101), il restait
-- 27 agrégats posés sur une table de fait depuis une surface d'affichage :
-- Meta 22, Instagram 3, Hypeddit 1, Revenu 1. Chacun réclamait une maille que
-- la couche or ne portait pas — et le comptage a suffi à les nommer.
--
-- CE N'EST PAS UNE VUE PAR TABLE, c'est une vue par QUESTION. `v_meta_daily`
-- existe parce que dix surfaces demandent « combien dépensé ce jour-là, pour
-- cette campagne » ; `v_meta_creative_daily` parce que trois demandent la même
-- chose par créative, et que la jointure vers `meta_ads` était recopiée trois
-- fois.

-- ── META, maille (locataire, compte, campagne, jour) ──────────────────────
-- Dix sites la demandaient : le PDF (5), la vue d'ensemble, les deux onglets
-- budget. `v_meta_spend_totals` (migration 101) reste le TOTAL ; celle-ci est
-- son grain temporel, exactement comme `v_platform_levels` l'est pour les
-- écoutes.
CREATE OR REPLACE VIEW v_meta_daily AS
    SELECT artist_id,
           ad_account_id,
           campaign_name,
           day_date AS day,
           COALESCE(SUM(spend), 0)::numeric              AS spend,
           COALESCE(SUM(results), 0)::bigint             AS results,
           COALESCE(SUM(impressions), 0)::bigint         AS impressions,
           COALESCE(SUM(reach), 0)::bigint               AS reach,
           COALESCE(SUM(custom_conversions), 0)::bigint  AS custom_conversions
      FROM meta_insights_performance_day
     WHERE artist_id IS NOT NULL
     GROUP BY artist_id, ad_account_id, campaign_name, day_date;

COMMENT ON VIEW v_meta_daily IS
    'Couche OR (ADR-019) : la performance Meta au grain (locataire, compte, '
    'campagne, jour). Le grain temporel de v_meta_spend_totals.';

-- ── META, maille CRÉATIVE ─────────────────────────────────────────────────
-- La jointure `meta_insights` × `meta_ads` était recopiée dans trois requêtes
-- de `meta_creatives.py`. Une jointure recopiée est une règle recopiée : il
-- suffit qu'une seule oublie `ma.artist_id` pour mélanger deux locataires.
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
           AVG(mi.ctr)                               AS ctr
      FROM meta_insights mi
      JOIN meta_ads ma ON ma.ad_id = mi.ad_id AND ma.artist_id = mi.artist_id
      -- LEFT : une créative dont la campagne a disparu du catalogue Meta reste une
      -- créative, et ses dépenses restent dépensées. Un INNER la ferait disparaître
      -- du total sans rien dire — la forme de défaut que ce dépôt paie le plus cher.
      LEFT JOIN meta_campaigns mc ON mc.campaign_id = ma.campaign_id
                                 AND mc.artist_id = ma.artist_id
     WHERE mi.artist_id IS NOT NULL
     GROUP BY mi.artist_id, ma.ad_name, mc.campaign_name, mi.date::date;

COMMENT ON VIEW v_meta_creative_daily IS
    'Couche OR (ADR-019) : la performance Meta au grain (locataire, créative, '
    'jour). Porte la jointure vers meta_ads, y compris son artist_id — elle '
    'était recopiée trois fois, et il suffit qu''une l''oublie pour mélanger '
    'deux locataires.';

-- ── INSTAGRAM, maille MOIS ────────────────────────────────────────────────
-- `date_trunc('month', timestamp)` était écrit deux fois, à l'identique. Et
-- `timestamp` est une date de PUBLICATION (clocks.Dates.PUBLICATION) : borner
-- dessus construit une cohorte de posts, pas une période d'activité. La vue
-- le nomme pour qu'on ne s'y trompe plus.
CREATE OR REPLACE VIEW v_instagram_media_monthly AS
    SELECT artist_id,
           date_trunc('month', timestamp)::date       AS month,
           COALESCE(SUM(like_count), 0)::bigint       AS likes,
           COALESCE(SUM(comments_count), 0)::bigint   AS comments,
           COUNT(*)::bigint                           AS posts
      FROM instagram_media
     WHERE artist_id IS NOT NULL AND timestamp IS NOT NULL
     GROUP BY artist_id, date_trunc('month', timestamp);

COMMENT ON VIEW v_instagram_media_monthly IS
    'Couche OR (ADR-019) : l''engagement Instagram par mois de PUBLICATION. '
    'C''est une cohorte de posts, pas une période d''activité.';

-- ── HYPEDDIT, maille (locataire, campagne, jour) ──────────────────────────
CREATE OR REPLACE VIEW v_hypeddit_daily AS
    SELECT artist_id,
           campaign_name,
           date AS day,
           COALESCE(SUM(visits), 0)::bigint AS visits,
           COALESCE(SUM(clicks), 0)::bigint AS clicks
      FROM hypeddit_daily_stats
     WHERE artist_id IS NOT NULL
     GROUP BY artist_id, campaign_name, date;

COMMENT ON VIEW v_hypeddit_daily IS
    'Couche OR (ADR-019) : Hypeddit au grain (locataire, campagne, jour).';
