-- Migration 008 — Email verification for saas_users
-- Run: Get-Content migrations/008_email_verification.sql | docker exec -i postgres_spotify_airflow psql -U postgres -d spotify_etl

ALTER TABLE saas_users
    ADD COLUMN IF NOT EXISTS email_verified    BOOLEAN   NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS verification_token TEXT      UNIQUE;

-- Admin accounts created via bootstrap are auto-verified
UPDATE saas_users SET email_verified = TRUE WHERE role = 'admin';

CREATE INDEX IF NOT EXISTS idx_saas_users_token
    ON saas_users(verification_token)
    WHERE verification_token IS NOT NULL;
