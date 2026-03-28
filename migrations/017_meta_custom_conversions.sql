-- Migration 017: Add custom_conversions column to Meta performance tables
--
-- Context: previously results = link_click + offsite_conversion.custom, causing
-- double-counting (fan clicks ad + Spotify button → counted twice).
-- custom_conversions = offsite_conversion.custom only (Spotify button clicks via
-- Hypeddit CAPI) — the metric Meta actually bills on.
-- results is now an alias for custom_conversions for backward compatibility.
--
-- Historical rows: custom_conversions = 0 (cannot be backfilled accurately since
-- old results was inflated). Values populate on next DAG run.

ALTER TABLE meta_insights_performance
    ADD COLUMN IF NOT EXISTS custom_conversions INT NOT NULL DEFAULT 0;

ALTER TABLE meta_insights_performance_day
    ADD COLUMN IF NOT EXISTS custom_conversions INT NOT NULL DEFAULT 0;

ALTER TABLE meta_insights_performance_age
    ADD COLUMN IF NOT EXISTS custom_conversions INT NOT NULL DEFAULT 0;

ALTER TABLE meta_insights_performance_country
    ADD COLUMN IF NOT EXISTS custom_conversions INT NOT NULL DEFAULT 0;

ALTER TABLE meta_insights_performance_placement
    ADD COLUMN IF NOT EXISTS custom_conversions INT NOT NULL DEFAULT 0;
