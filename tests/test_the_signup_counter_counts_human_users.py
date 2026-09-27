"""R222 — the admin signup counter counts HUMAN users (owner's decision, 2026-09-27).

A user of the sandbox or the canary tenant is not a signup; a user not yet linked to an
artist (`artist_id` NULL) is one. An inner JOIN would drop the second — the exact
regression the owner asked to avoid (code-critic, R222).
"""
import pytest

pytestmark = pytest.mark.xdist_group("signup-counter")


def _db():
    from src.database.postgres_handler import PostgresHandler
    try:
        return PostgresHandler.from_env_or_config()
    except Exception:                                  # noqa: BLE001
        pytest.skip("no live database")


def _total(db, sql) -> int:
    return int(db.fetch_query(sql)[0][3])


def test_a_sandbox_user_is_not_counted_and_an_unlinked_user_is():
    from src.dashboard.views.admin import signups_sql
    db = _db()
    before = _total(db, signups_sql())
    tenant = db.fetch_query(
        "INSERT INTO saas_artists (name, slug, tier, active, is_sandbox) "
        "VALUES ('R222 sandbox', 'r222-sandbox-guard', 'free', TRUE, TRUE) RETURNING id")[0][0]
    try:
        db.execute_query(
            "INSERT INTO saas_users (username, email, role, artist_id, password_hash) VALUES "
            "('r222-sandbox', 'r222-sandbox@example.invalid', 'artist', %s, 'x'), "
            "('r222-unlinked', 'r222-unlinked@example.invalid', 'artist', NULL, 'x')", (tenant,))
        assert _total(db, signups_sql()) == before + 1, (
            "exactly the unlinked human user must be added — not the sandbox one")
        # Non-vacuity: the pre-R222 query counts BOTH.
        raw = "SELECT 0, 0, 0, COUNT(*) FROM saas_users WHERE role <> 'admin'"
        assert _total(db, raw) - _total(db, signups_sql()) >= 1
    finally:
        db.execute_query("DELETE FROM saas_users WHERE email LIKE 'r222-%%@example.invalid'")
        db.execute_query("DELETE FROM saas_artists WHERE id = %s", (tenant,))
        db.close()
