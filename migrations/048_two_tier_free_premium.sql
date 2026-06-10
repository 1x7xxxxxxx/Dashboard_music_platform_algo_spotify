-- Migration 048 — Collapse to 2 tiers: free + premium (retire 'basic')
-- Run: make migrate   (or, from PowerShell, see CLAUDE.md § Running Migrations)
--
-- Decision 2026-06-09: only Free (0€) and Premium (10€). The former Basic (5€)
-- is merged into Premium (ML + everything). This migrates every existing 'basic'
-- reference onto 'premium' and deactivates the basic plan row (kept, not deleted,
-- to preserve historical FK references in artist_subscriptions / plan history).

-- 1) Re-point active subscriptions from basic → premium.
UPDATE artist_subscriptions
SET plan_id = (SELECT id FROM subscription_plans WHERE name = 'premium'),
    updated_at = NOW()
WHERE plan_id = (SELECT id FROM subscription_plans WHERE name = 'basic');

-- 2) Legacy tier + promo columns on saas_artists.
UPDATE saas_artists SET tier = 'premium'       WHERE tier = 'basic';
UPDATE saas_artists SET promo_plan = 'premium' WHERE promo_plan = 'basic';

-- 3) Premium price is now 10€ (unchanged), free stays 0€.
UPDATE subscription_plans SET price_monthly = 10.00, max_artists = 10 WHERE name = 'premium';

-- 4) Retire the basic plan row (no longer offered) without breaking FKs.
UPDATE subscription_plans SET active = FALSE WHERE name = 'basic';

-- 5) saas_artists.tier: default must be 'free' (new signups) and the CHECK must
--    ALLOW 'free' — the old constraint (IN basic/premium) rejected 'free', which
--    silently broke registration (register.py inserts tier='free') and would have
--    given post-trial users premium via the tier fallback. Done after step 2 so no
--    'basic' rows remain to violate the new constraint.
ALTER TABLE saas_artists ALTER COLUMN tier SET DEFAULT 'free';
ALTER TABLE saas_artists DROP CONSTRAINT IF EXISTS saas_artists_tier_check;
ALTER TABLE saas_artists ADD CONSTRAINT saas_artists_tier_check
    CHECK (tier IN ('free', 'premium'));
