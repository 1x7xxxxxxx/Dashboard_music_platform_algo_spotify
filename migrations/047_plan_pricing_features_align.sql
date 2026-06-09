-- Migration 047 — Align subscription_plans (prices + features) with PLAN_FEATURES/PLAN_CATALOG
-- Run: make migrate   (or, from PowerShell, see CLAUDE.md § Running Migrations)
--
-- Reconciles the DB row prices + features JSON with the code-side single source of
-- truth (src/database/stripe_schema.py: PLAN_FEATURES + PLAN_CATALOG), after the
-- 2026-06-09 tier review:
--   * Basic = 5 €, Premium = 10 € (was 5 € / 15 € from migration 014).
--   * Export PDF moved to FREE ; Revenue forecast moved to PREMIUM-only.
-- NOTE: the `features` JSON is a display/audit mirror — runtime gating uses
-- PLAN_FEATURES in code, which stays authoritative.

UPDATE subscription_plans SET price_monthly = 0.00,  max_artists = 1  WHERE name = 'free';
UPDATE subscription_plans SET price_monthly = 5.00,  max_artists = 3  WHERE name = 'basic';
UPDATE subscription_plans SET price_monthly = 10.00, max_artists = 10 WHERE name = 'premium';

UPDATE subscription_plans
SET features = '["home","spotify_s4a_combined","youtube","meta_ads_overview","instagram","soundcloud","apple_music","hypeddit","imusician","upload_csv","credentials","export_csv","export_pdf","data_wrapped","meta_mapping","referral"]'
WHERE name = 'free';

UPDATE subscription_plans
SET features = '["home","spotify_s4a_combined","youtube","meta_ads_overview","instagram","soundcloud","apple_music","hypeddit","imusician","upload_csv","credentials","export_csv","export_pdf","data_wrapped","meta_mapping","referral","trigger_algo"]'
WHERE name = 'basic';

UPDATE subscription_plans SET features = '["*"]' WHERE name = 'premium';
