-- ═══════════════════════════════════════════════════════════════════════════
-- 109 — Meta : la tuile « Dépenses » affichait le double
-- ═══════════════════════════════════════════════════════════════════════════
-- ⚠️ DÉFAUT VIVANT, mesuré le 2026-09-12. Pour l'artiste 1 :
--
--     tuile « Dépenses » (meta_ads_overview)   6 165,65 €
--     couche or (v_meta_daily)                 3 087,82 €
--
-- `meta_insights_performance` porte DEUX générations de lignes :
--
--   * 231 lignes QUOTIDIENNES, une par (campagne, jour), écrites par la boucle
--     `time_increment=1` de `_meta_insight_fetch.py`. C'est la forme actuelle, et
--     chacune a sa jumelle dans `meta_insights_performance_day`, écrite dans la
--     MÊME itération.
--   * 21 lignes de CUMUL À VIE, une par campagne, `date_start` = le jour de la
--     collecte (2025-12-15), vestige d'un collecteur antérieur. Aucune jumelle.
--
-- Les sommer ensemble compte chaque euro deux fois. Le PDF avait été corrigé — et
-- la leçon est écrite, mot pour mot, dans un commentaire de
-- `pdf_exporter/_collectors.py:329` : « meta_insights_performance double-comptait
-- les fenêtres (≈2× le spend réel) ». La classe est restée vivante dans SIX autres
-- surfaces. Un commentaire ne garde rien ; c'est la démonstration.
--
-- Le pire cas est `meta_ads_overview` : il lit les lignes brutes et les somme EN
-- PANDAS. Aucun garde SQL ne peut voir cet agrégat — il n'y a pas de `SUM(` dans
-- la requête.
--
-- LA RÈGLE, et pourquoi elle est structurelle et non une date devinée
-- ------------------------------------------------------------------
-- Une ligne quotidienne a, par construction, sa jumelle dans
-- `meta_insights_performance_day` : la boucle du collecteur écrit les deux dans la
-- même itération. Une ligne de cumul n'en a pas. Le prédicat est donc
-- « la jumelle existe », pas « date_start > un seuil » — un seuil se périme, et
-- une ligne quotidienne légitime du jour même porterait la même date que sa
-- collecte.
--
-- Vérifié : 252 lignes, 231 avec jumelle, 21 sans, et 231 = le compte exact de
-- `meta_insights_performance_day`.
--
-- Cette vue existe parce que `_day` ne porte PAS `link_clicks`, `lp_views`,
-- `frequency` ni `ctr` : `v_meta_daily` ne peut donc pas servir les surfaces qui
-- les affichent. C'est la même mesure, avec les colonnes en plus.
CREATE OR REPLACE VIEW v_meta_campaign_daily AS
    SELECT p.artist_id,
           p.ad_account_id,
           p.campaign_name,
           p.date_start                              AS day,
           COALESCE(p.spend, 0)::numeric             AS spend,
           COALESCE(p.results, 0)::bigint            AS results,
           COALESCE(p.custom_conversions, 0)::bigint AS custom_conversions,
           COALESCE(p.impressions, 0)::bigint        AS impressions,
           COALESCE(p.reach, 0)::bigint              AS reach,
           COALESCE(p.link_clicks, 0)::bigint        AS link_clicks,
           COALESCE(p.lp_views, 0)::bigint           AS lp_views,
           p.frequency,
           p.ctr,
           p.cpr,
           p.cpm,
           p.cpc,
           p.collected_at
      FROM meta_insights_performance p
     WHERE p.artist_id IS NOT NULL
       AND EXISTS (
           SELECT 1 FROM meta_insights_performance_day d
            WHERE d.artist_id     = p.artist_id
              AND d.campaign_name = p.campaign_name
              AND d.day_date      = p.date_start);

COMMENT ON VIEW v_meta_campaign_daily IS
    'Couche OR (ADR-019) : la performance Meta au grain (locataire, campagne, '
    'jour), AVEC les colonnes que meta_insights_performance_day ne porte pas '
    '(link_clicks, lp_views, frequency, ctr). Écarte les lignes de cumul à vie '
    'd''un collecteur antérieur, qui faisaient afficher le double (migration 109).';
