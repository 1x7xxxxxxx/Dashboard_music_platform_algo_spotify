-- Migration 046 — Onboarding analytics report dispatch tracking
-- Run: make migrate   (or, from PowerShell, see CLAUDE.md § Running Migrations)
--
-- Adds a single-shot timestamp so the onboarding_report DAG sends the first
-- analytics PDF report exactly once per user, after their first successful
-- collection (S4A data present). NULL = not yet sent.

ALTER TABLE saas_users
    ADD COLUMN IF NOT EXISTS onboarding_report_sent_at TIMESTAMPTZ;

COMMENT ON COLUMN saas_users.onboarding_report_sent_at IS
    'When the post-first-collection onboarding analytics PDF was emailed. '
    'NULL = pending; set by the onboarding_report DAG to guarantee a single send.';

-- Admins never receive the onboarding report (no client journey).
UPDATE saas_users
SET onboarding_report_sent_at = now()
WHERE role = 'admin' AND onboarding_report_sent_at IS NULL;

-- Partial index: the DAG scans only users still awaiting their report.
CREATE INDEX IF NOT EXISTS idx_saas_users_onboarding_report_pending
    ON saas_users(id)
    WHERE onboarding_report_sent_at IS NULL;
