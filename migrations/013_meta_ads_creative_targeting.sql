-- Migration 013: Creative content columns + adset targeting decomposition
-- Required by MetaAdsApiCollector full rewrite (Brick 23 — full history mode).

-- 1. Add creative content columns to meta_ads
ALTER TABLE meta_ads ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE meta_ads ADD COLUMN IF NOT EXISTS body TEXT;
ALTER TABLE meta_ads ADD COLUMN IF NOT EXISTS call_to_action VARCHAR(100);

-- 2. Add decomposed targeting columns to meta_adsets
--    These mirror the CSV watcher flat columns and allow cross-source joins.
ALTER TABLE meta_adsets ADD COLUMN IF NOT EXISTS countries TEXT;
ALTER TABLE meta_adsets ADD COLUMN IF NOT EXISTS cities TEXT;
ALTER TABLE meta_adsets ADD COLUMN IF NOT EXISTS gender TEXT;
ALTER TABLE meta_adsets ADD COLUMN IF NOT EXISTS age_min TEXT;
ALTER TABLE meta_adsets ADD COLUMN IF NOT EXISTS age_max TEXT;
ALTER TABLE meta_adsets ADD COLUMN IF NOT EXISTS flexible_inclusions TEXT;
ALTER TABLE meta_adsets ADD COLUMN IF NOT EXISTS advantage_audience TEXT;
ALTER TABLE meta_adsets ADD COLUMN IF NOT EXISTS publisher_platforms TEXT;
ALTER TABLE meta_adsets ADD COLUMN IF NOT EXISTS instagram_positions TEXT;
ALTER TABLE meta_adsets ADD COLUMN IF NOT EXISTS device_platforms TEXT;
