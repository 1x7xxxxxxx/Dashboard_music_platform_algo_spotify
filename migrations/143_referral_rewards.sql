-- 143 — referral_rewards : the free month a referrer EARNS when the artist they referred
-- pays for the first time, and its application as a Stripe coupon (R272, 2026-09-28).
--
-- Additive only (CREATE TABLE IF NOT EXISTS) — idempotent, safe to replay.
--
-- Why a table and not the counter alone (code-critic R272 a) : Stripe retries a webhook
-- until it gets a 2xx, and the same `invoice.paid` can arrive twice. The counter
-- `saas_artists.referral_free_months` incremented twice would give two months for one
-- referral. `earned_event_id` UNIQUE makes the second delivery a no-op, and
-- `referred_artist_id` UNIQUE makes one referral earn once, whatever the events.
--
-- States: pending (earned, not yet on a subscription — the referrer has none yet, or no
-- coupon is configured) → applied (coupon set on the referrer's subscription) →
-- consumed (the referrer's next paid invoice carried the discount).
CREATE TABLE IF NOT EXISTS referral_rewards (
    id                     SERIAL PRIMARY KEY,
    referrer_artist_id     INTEGER NOT NULL REFERENCES saas_artists(id),
    referred_artist_id     INTEGER NOT NULL REFERENCES saas_artists(id),
    earned_event_id        TEXT NOT NULL UNIQUE,
    status                 TEXT NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending', 'applied', 'consumed')),
    stripe_subscription_id TEXT,
    coupon_id              TEXT,
    detail                 TEXT,
    earned_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    applied_at             TIMESTAMPTZ,
    consumed_at            TIMESTAMPTZ,
    UNIQUE (referred_artist_id)
);

CREATE INDEX IF NOT EXISTS idx_referral_rewards_referrer_status
    ON referral_rewards (referrer_artist_id, status);
