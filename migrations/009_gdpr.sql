-- Migration 009: GDPR compliance fields
-- Adds explicit consent tracking (CGU + marketing opt-in) to saas_users.

ALTER TABLE saas_users
    ADD COLUMN IF NOT EXISTS terms_accepted      BOOLEAN     NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS terms_accepted_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS marketing_consent   BOOLEAN     NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS marketing_consent_at TIMESTAMPTZ;

-- Pre-migration users (created before this system) are marked as accepted.
-- They must be informed retroactively if the platform goes public.
UPDATE saas_users
SET terms_accepted = TRUE,
    terms_accepted_at = NOW()
WHERE terms_accepted = FALSE;

-- Index for efficient opt-in list queries (email campaigns)
CREATE INDEX IF NOT EXISTS idx_saas_users_marketing
    ON saas_users (marketing_consent, active)
    WHERE marketing_consent = TRUE AND active = TRUE;
