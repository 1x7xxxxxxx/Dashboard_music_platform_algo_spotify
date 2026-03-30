-- Migration 015: Admin promo codes
-- Allows admins to create single-use or limited-use codes that grant
-- free access to Basic or Premium for a fixed duration (e.g. 30 days).
-- Distinct from the referral system (migration 014).

-- ── Promo codes master table ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS promo_codes (
    id            SERIAL PRIMARY KEY,
    code          VARCHAR(20)  NOT NULL UNIQUE,
    plan_target   VARCHAR(20)  NOT NULL CHECK (plan_target IN ('basic', 'premium')),
    duration_days INTEGER      NOT NULL DEFAULT 30,
    max_uses      INTEGER      NOT NULL DEFAULT 1,   -- 0 = unlimited
    uses_count    INTEGER      NOT NULL DEFAULT 0,
    active        BOOLEAN      NOT NULL DEFAULT TRUE,
    expires_at    TIMESTAMPTZ,                        -- NULL = code never expires on its own
    notes         TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_promo_codes_code   ON promo_codes(code);
CREATE INDEX IF NOT EXISTS idx_promo_codes_active ON promo_codes(active) WHERE active = TRUE;

-- ── Usage log ──────────────────────────────────────────────────────────────
-- One row per artist who redeemed a promo code.
CREATE TABLE IF NOT EXISTS promo_events (
    id            SERIAL PRIMARY KEY,
    promo_code_id INTEGER      NOT NULL REFERENCES promo_codes(id),
    artist_id     INTEGER      NOT NULL UNIQUE REFERENCES saas_artists(id),
    applied_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_promo_events_promo  ON promo_events(promo_code_id);
CREATE INDEX IF NOT EXISTS idx_promo_events_artist ON promo_events(artist_id);

-- ── saas_artists extensions ────────────────────────────────────────────────
ALTER TABLE saas_artists
    ADD COLUMN IF NOT EXISTS promo_code_used      VARCHAR(20),
    ADD COLUMN IF NOT EXISTS promo_plan           VARCHAR(20),
    ADD COLUMN IF NOT EXISTS promo_plan_expires_at TIMESTAMPTZ;
