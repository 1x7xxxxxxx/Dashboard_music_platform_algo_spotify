-- Migration 012: Meta Ads API collector + data quality fixes
-- Fixes: artist_id in meta_insights UNIQUE, dedup performance tables,
--        backfill artist_id=1 for rows inserted before multi-tenancy.

-- 1. Backfill artist_id=1 where null (legacy rows from v1 import)
UPDATE meta_insights SET artist_id = 1 WHERE artist_id IS NULL;

-- 2. Fix meta_insights UNIQUE: was (ad_id, date), now (artist_id, ad_id, date)
--    Deduplicate first: keep row with lowest id per group
DELETE FROM meta_insights a
USING meta_insights b
WHERE a.id > b.id
  AND a.artist_id = b.artist_id
  AND a.ad_id = b.ad_id
  AND a.date = b.date;

ALTER TABLE meta_insights DROP CONSTRAINT IF EXISTS meta_insights_ad_id_date_key;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'meta_insights_artist_ad_date_key'
    ) THEN
        ALTER TABLE meta_insights ADD CONSTRAINT meta_insights_artist_ad_date_key
            UNIQUE (artist_id, ad_id, date);
    END IF;
END$$;

-- 3. Deduplicate meta_insights_performance (keep lowest id per UNIQUE group)
DELETE FROM meta_insights_performance a
USING meta_insights_performance b
WHERE a.id > b.id
  AND a.artist_id = b.artist_id
  AND a.campaign_name = b.campaign_name
  AND a.date_start = b.date_start;

-- 4. Deduplicate meta_insights_performance_day
DELETE FROM meta_insights_performance_day a
USING meta_insights_performance_day b
WHERE a.id > b.id
  AND a.artist_id = b.artist_id
  AND a.campaign_name = b.campaign_name
  AND a.day_date = b.day_date;

-- 5. Deduplicate meta_insights_performance_age
DELETE FROM meta_insights_performance_age a
USING meta_insights_performance_age b
WHERE a.id > b.id
  AND a.artist_id = b.artist_id
  AND a.campaign_name = b.campaign_name
  AND a.age_range = b.age_range;

-- 6. Deduplicate meta_insights_performance_country
DELETE FROM meta_insights_performance_country a
USING meta_insights_performance_country b
WHERE a.id > b.id
  AND a.artist_id = b.artist_id
  AND a.campaign_name = b.campaign_name
  AND a.country = b.country;

-- 7. Deduplicate meta_insights_performance_placement
DELETE FROM meta_insights_performance_placement a
USING meta_insights_performance_placement b
WHERE a.id > b.id
  AND a.artist_id = b.artist_id
  AND a.campaign_name = b.campaign_name
  AND a.platform = b.platform
  AND a.placement = b.placement;

-- 8. Add missing columns to meta_adsets (CSV watcher created table with flat targeting columns;
--    API collector needs structured columns)
ALTER TABLE meta_adsets ADD COLUMN IF NOT EXISTS optimization_goal VARCHAR(100);
ALTER TABLE meta_adsets ADD COLUMN IF NOT EXISTS billing_event VARCHAR(50);
ALTER TABLE meta_adsets ADD COLUMN IF NOT EXISTS daily_budget DECIMAL(10,2);
ALTER TABLE meta_adsets ADD COLUMN IF NOT EXISTS lifetime_budget DECIMAL(10,2);
ALTER TABLE meta_adsets ADD COLUMN IF NOT EXISTS end_time TIMESTAMP;
ALTER TABLE meta_adsets ADD COLUMN IF NOT EXISTS targeting JSONB;

-- 9. Add missing columns to meta_ads (CSV watcher used creative fields; API collector uses status/timing)
ALTER TABLE meta_ads ADD COLUMN IF NOT EXISTS status VARCHAR(50);
ALTER TABLE meta_ads ADD COLUMN IF NOT EXISTS creative_id VARCHAR(50);
ALTER TABLE meta_ads ADD COLUMN IF NOT EXISTS created_time TIMESTAMP;
ALTER TABLE meta_ads ADD COLUMN IF NOT EXISTS updated_time TIMESTAMP;
