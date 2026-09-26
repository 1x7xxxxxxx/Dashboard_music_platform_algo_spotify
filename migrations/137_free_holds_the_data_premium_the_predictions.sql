-- ============================================================
-- 137 — Free = tes données et leur fusion ; Premium = les prédictions (ADR-029)
-- ============================================================
--
-- `subscription_plans.features` suit `PLAN_FEATURES` (règle posée par 085). Le 2026-09-26
-- la fusion Meta × plateformes (`meta_x_spotify`, `meta_creatives`, `meta_breakdowns`), le
-- rapport PDF à la demande (`export_pdf`) et l'aperçu de Road to Algo (`algo_preview`)
-- rejoignent Free. `tests/test_plan_catalog_matches_the_gating.py` lit la DERNIÈRE migration
-- qui fixe cette ligne.
UPDATE subscription_plans
   SET features = '["home","spotify_s4a_combined","youtube","meta_ads_overview","instagram","soundcloud","apple_music","hypeddit","imusician","upload_csv","credentials","export_csv","data_wrapped","meta_mapping","referral","meta_x_spotify","meta_creatives","meta_breakdowns","export_pdf","algo_preview"]'::jsonb
 WHERE name = 'free';
