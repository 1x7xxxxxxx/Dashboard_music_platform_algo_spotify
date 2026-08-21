-- ============================================================
-- 071 — schema_migrations: the ledger that says what already ran
-- ============================================================
-- Introduced 2026-08-21 alongside tools/migrate.sh. ADR-002 §Ré-évaluation
-- explains why this replaces Alembic rather than adopting it: autogenerate needs
-- SQLAlchemy models and this repo has none, so a framework would buy ceremony,
-- not safety. What was actually missing was a record of what had been applied —
-- without it the only possible strategy was "reapply all 70 files every time".
--
-- It lives in a migration, not only in the runner, so the CANONICAL schema
-- (init_db.sql + migrations/*.sql) contains it too. Created only by the runner,
-- it showed up as permanent drift in `make schema-check` — a check reporting a
-- difference that is not one is a check people learn to ignore.
--
-- `checksum` is the sha256 of the file as applied: a migration edited after the
-- fact is then detectable, and is deliberately NOT replayed.

CREATE TABLE IF NOT EXISTS schema_migrations (
    filename   TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum   TEXT NOT NULL
);
