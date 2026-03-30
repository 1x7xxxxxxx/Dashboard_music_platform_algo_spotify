-- Brick 26/28: TOTP 2FA columns + session rate-limit tracking
-- Brick 27: GDPR Art. 17 erasure audit log

-- 2FA columns
ALTER TABLE saas_users
    ADD COLUMN IF NOT EXISTS totp_secret  TEXT,
    ADD COLUMN IF NOT EXISTS totp_enabled BOOLEAN NOT NULL DEFAULT FALSE;

-- Session-based rate limit tracking (login + register endpoints)
-- ip_hash is a SHA-256 of the client IP (or session_id when IP unavailable).
-- Rows are pruned after window_start + 1 hour.
CREATE TABLE IF NOT EXISTS login_rate_limit (
    id             BIGSERIAL    PRIMARY KEY,
    ip_hash        TEXT         NOT NULL,
    endpoint       TEXT         NOT NULL DEFAULT 'login',
    attempts       INT          NOT NULL DEFAULT 1,
    window_start   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(ip_hash, endpoint)
);
CREATE INDEX IF NOT EXISTS idx_login_rate_ip ON login_rate_limit(ip_hash, endpoint);

-- GDPR Art. 17 erasure audit log
-- One row per erasure event; rows_deleted is a JSON summary {table: count}.
CREATE TABLE IF NOT EXISTS gdpr_erasure_log (
    id               BIGSERIAL    PRIMARY KEY,
    admin_user_id    INT,
    erased_artist_id INT          NOT NULL,
    erased_username  TEXT,
    erased_email     TEXT,
    rows_deleted     JSONB,
    reason           TEXT,
    executed_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
