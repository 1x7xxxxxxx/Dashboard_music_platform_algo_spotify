-- Migration 010: Update subscription_plans.features JSONB to match PLAN_FEATURES in stripe_schema.py
-- This column is informational only (shown in billing view).
-- Enforcement is done exclusively via the PLAN_FEATURES Python dict in src/database/stripe_schema.py.

UPDATE subscription_plans
SET features = '["home","spotify_s4a_combined","youtube"]'::jsonb
WHERE name = 'free';

UPDATE subscription_plans
SET features = '["home","spotify_s4a_combined","youtube","meta_ads_overview","instagram","soundcloud","apple_music","hypeddit","imusician","upload_csv","credentials","export_csv","data_wrapped"]'::jsonb
WHERE name = 'basic';

-- premium stays as ["*"] — no change needed
