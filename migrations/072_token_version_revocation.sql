-- ============================================================
-- 072 — saas_users.token_version: make a revocation actually revoke
-- ============================================================
-- R24, 2026-08-22. Until now nothing invalidated a session that already existed:
--
--   * `admin.py:_toggle_user_active` set `active = FALSE`, but `active` was read
--     only inside the LOGIN query. A deactivated tenant kept the dashboard for as
--     long as they kept clicking (idle timeout: 60 min) and the API for up to 24 h.
--   * `account.py` changed `password_hash`, and the attacker who had triggered the
--     password change kept their own session — the one gesture every incident
--     runbook tells a user to perform did nothing to the intruder.
--
-- The JWT is stateless by construction, so the only way to revoke one without
-- inventing a denylist store is to carry a counter in the token and compare it to
-- the row on every request. Bump the column, and every token issued before the bump
-- fails its comparison. One integer, no expiry bookkeeping, no second datastore —
-- the reasoning ADR-002 already applies to Alembic and Redis.
--
-- DEFAULT 0 and NOT NULL: tokens issued before this migration carry no `tv` claim,
-- and the check treats a missing claim as 0, so they keep working until they expire
-- (24 h). Deploying this does not sign everyone out.

ALTER TABLE saas_users
    ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0;

COMMENT ON COLUMN saas_users.token_version IS
    'Bumped on deactivation and on password change. A JWT whose tv claim is lower '
    'is refused (src/api/deps.py). Never decremented.';
