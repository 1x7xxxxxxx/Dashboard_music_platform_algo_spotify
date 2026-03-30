-- Migration 014: Referral / coupon system
-- Creates referral_codes and referral_events tables,
-- extends saas_artists with referral tracking columns,
-- and updates subscription prices to Basic=5€ / Premium=15€.

-- ── Referral codes ─────────────────────────────────────────────────────────
-- One unique code per artist, generated on first visit to the referral page.
CREATE TABLE IF NOT EXISTS referral_codes (
    id          SERIAL PRIMARY KEY,
    artist_id   INTEGER NOT NULL UNIQUE REFERENCES saas_artists(id) ON DELETE CASCADE,
    code        VARCHAR(20) NOT NULL UNIQUE,
    uses_count  INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_referral_codes_code     ON referral_codes(code);
CREATE INDEX IF NOT EXISTS idx_referral_codes_artist   ON referral_codes(artist_id);

-- ── Referral events ────────────────────────────────────────────────────────
-- One row per successful referral (new artist registered with a valid code).
CREATE TABLE IF NOT EXISTS referral_events (
    id                  SERIAL PRIMARY KEY,
    referrer_artist_id  INTEGER NOT NULL REFERENCES saas_artists(id),
    referred_artist_id  INTEGER NOT NULL UNIQUE REFERENCES saas_artists(id),
    code_used           VARCHAR(20) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_referral_events_referrer  ON referral_events(referrer_artist_id);
CREATE INDEX IF NOT EXISTS idx_referral_events_referred  ON referral_events(referred_artist_id);

-- ── saas_artists extensions ────────────────────────────────────────────────
ALTER TABLE saas_artists
    ADD COLUMN IF NOT EXISTS referred_by_code         VARCHAR(20),
    ADD COLUMN IF NOT EXISTS referral_free_months     INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS first_month_discount_pct INTEGER NOT NULL DEFAULT 0;

-- ── Pricing update ─────────────────────────────────────────────────────────
UPDATE subscription_plans SET price_monthly = 5.00  WHERE name = 'basic';
UPDATE subscription_plans SET price_monthly = 15.00 WHERE name = 'premium';
