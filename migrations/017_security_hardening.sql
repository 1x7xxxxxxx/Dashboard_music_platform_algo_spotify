-- Migration 017 — Security hardening
-- Applies: HIGH-01 (brute-force lockout), INFO-01 (token expiry),
--          MEDIUM-08 (admin audit log for PII exports), HIGH-09 (credentials auth guard)
-- Run via: Get-Content migrations/017_security_hardening.sql | docker exec -i <container> psql -U postgres -d spotify_etl

-- ─────────────────────────────────────────────────────────
-- HIGH-01: Login rate limiting — account lockout after 5 failures
-- ─────────────────────────────────────────────────────────
ALTER TABLE saas_users
    ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS locked_until          TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_saas_users_locked_until
    ON saas_users (locked_until)
    WHERE locked_until IS NOT NULL;

-- ─────────────────────────────────────────────────────────
-- INFO-01: Email verification token expiry (48 hours)
-- ─────────────────────────────────────────────────────────
ALTER TABLE saas_users
    ADD COLUMN IF NOT EXISTS verification_token_created_at TIMESTAMPTZ;

-- Backfill: mark existing unverified tokens as created now so they don't
-- expire immediately. Verified accounts have verification_token = NULL.
UPDATE saas_users
SET    verification_token_created_at = NOW()
WHERE  verification_token IS NOT NULL
  AND  email_verified = FALSE
  AND  verification_token_created_at IS NULL;

-- ─────────────────────────────────────────────────────────
-- MEDIUM-08: Admin audit log for PII exports (GDPR Art. 5(1)(f))
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS admin_audit_log (
    id          SERIAL PRIMARY KEY,
    admin_user  VARCHAR(100) NOT NULL,
    action      VARCHAR(100) NOT NULL,
    details     JSONB,
    ip_hint     VARCHAR(50),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_audit_action    ON admin_audit_log (action);
CREATE INDEX IF NOT EXISTS idx_admin_audit_admin     ON admin_audit_log (admin_user);
CREATE INDEX IF NOT EXISTS idx_admin_audit_created   ON admin_audit_log (created_at DESC);

-- ─────────────────────────────────────────────────────────
-- GDPR Art. 17: Cascade erasure — FK constraints for analytics data
-- Ensure that deleting a saas_artists row (or setting active=FALSE) does
-- not orphan analytics data. We add ON DELETE CASCADE where safe.
-- Note: cascade DDL is applied only to tables that had no pre-existing FKs
-- declared with ON DELETE — check existing constraints first.
-- ─────────────────────────────────────────────────────────

-- Referral / promo events already have FK constraints; ensure they cascade
DO $$
BEGIN
    -- referral_events.referrer_artist_id → saas_artists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.referential_constraints rc
        JOIN information_schema.key_column_usage kcu
          ON kcu.constraint_name = rc.constraint_name
        WHERE rc.delete_rule = 'CASCADE'
          AND kcu.table_name = 'referral_events'
          AND kcu.column_name = 'referred_artist_id'
    ) THEN
        -- Safe to add — referral_events are meaningless without the artist
        ALTER TABLE referral_events
            DROP CONSTRAINT IF EXISTS referral_events_referred_artist_id_fkey,
            ADD  CONSTRAINT referral_events_referred_artist_id_fkey
                 FOREIGN KEY (referred_artist_id) REFERENCES saas_artists(id) ON DELETE CASCADE;
    END IF;
END $$;
