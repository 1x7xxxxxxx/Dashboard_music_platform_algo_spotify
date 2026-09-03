-- 081 — Per-feature opt-out for the weekly recap e-mail.
--
-- Why a dedicated column rather than reusing `marketing_consent` (migration 009).
--
-- A weekly recap of the CUSTOMER'S OWN numbers, for a feature they pay for, is a
-- SERVICE e-mail, not prospecting. This repo already draws that line: the
-- verification e-mail is deliberately exempt from the artist-audience gate because
-- "c'est le consentement qui fait la différence, pas le destinataire".
--
-- `marketing_consent` defaults to FALSE and is only ever set at signup. Gating the
-- digest on it would mean **the majority of premium tenants never receive what they
-- bought**, with nothing anywhere reporting it — the shape of defect this repo keeps
-- finding: correct code that nothing reaches.
--
-- NULL = enrolled. The unsubscribe link sets it. The marketing flag keeps meaning
-- marketing, and withdrawal becomes auditable per feature.
--
-- Shape follows migration 046 (`onboarding_report_sent_at`), the existing precedent
-- for a per-feature dispatch-state column on saas_users.

ALTER TABLE saas_users
    ADD COLUMN IF NOT EXISTS weekly_digest_optout_at TIMESTAMPTZ;

COMMENT ON COLUMN saas_users.weekly_digest_optout_at IS
    'When this user opted out of the weekly recap. NULL = still enrolled. Distinct '
    'from marketing_consent: the digest is a service e-mail for a paid feature.';

-- The digest reads: artist_id = %s AND active AND email_verified AND role = 'artist'
-- AND weekly_digest_optout_at IS NULL. Partial index on exactly that shape.
CREATE INDEX IF NOT EXISTS idx_saas_users_digest_enrolled
    ON saas_users (artist_id)
    WHERE active AND email_verified AND weekly_digest_optout_at IS NULL;
