"""Guard: a failed login is counted by the DATABASE, not read then rewritten (R370 a).

Type: Utility
Uses: ast, threading, bcrypt, live Postgres
Triggers: pytest
Persists in: un compte jetable, effacé en fin de test

Error class `check-then-insert-loses-the-race`, sibling found by the 2026-10-05 sweep.

Both login paths read `failed_login_attempts` with the user row, ran bcrypt, then wrote
`fail_count + 1` back. Eight wrong passwords sent at once all read 0 and all wrote 1:
the lockout threshold of 5 was never reached, so a parallel brute force ran unbounded.
The fix lets Postgres increment and lock in ONE statement (`src/utils/login_lockout.py`).
"""
from __future__ import annotations

import ast
import os
import socket
import threading
import uuid
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LOGIN_PATHS = (REPO / "src/dashboard/auth.py", REPO / "src/api/auth.py")


def rewritten_counters(source: str) -> list[int]:
    """Lines whose SQL SETS the counter to a value computed in Python. Pure."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if "failed_login_attempts = %s" in node.value:
                out.append(node.lineno)
        elif isinstance(node, ast.JoinedStr):
            text = "".join(v.value for v in node.values
                           if isinstance(v, ast.Constant) and isinstance(v.value, str))
            if "failed_login_attempts = %s" in text:
                out.append(node.lineno)
    return out


def test_no_login_path_rewrites_the_counter_from_python() -> None:
    bad = {p.name: lines for p in LOGIN_PATHS
           if (lines := rewritten_counters(p.read_text(encoding="utf-8")))}
    assert not bad, (
        f"{bad}: the failure counter is written from a value read earlier — two "
        "concurrent wrong passwords count as one. Call record_password_failure().")


def test_the_detector_sees_a_rewritten_counter() -> None:
    old = 'db.execute_query("UPDATE saas_users SET failed_login_attempts = %s WHERE id = %s")\n'
    assert rewritten_counters(old) == [1]
    split = ('q = ("UPDATE saas_users SET failed_login_attempts = %s, "\n'
             '     "locked_until = NOW() WHERE id = %s")\n')
    assert rewritten_counters(split) == [1]
    ok = 'db.execute_query("UPDATE saas_users SET failed_login_attempts = 0 WHERE id = %s")\n'
    assert rewritten_counters(ok) == []


def _db():
    if not os.environ.get("DATABASE_URL"):
        try:
            with socket.create_connection(("127.0.0.1", 5433), timeout=1.5):
                pass
        except OSError:
            return None
    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        db.fetch_query("SELECT 1 FROM saas_users LIMIT 1")
        return db
    except Exception:  # noqa: BLE001
        return None


@pytest.mark.skipif(_db() is None, reason="needs the provisioned DB")
def test_eight_concurrent_wrong_passwords_lock_the_account() -> None:
    """La mesure : huit mauvais mots de passe simultanés sur l'API."""
    import bcrypt

    from src.api.auth import authenticate_api_user
    from src.dashboard.utils import get_db_connection

    admin = _db()
    name = f"race-login-{uuid.uuid4().hex[:8]}"
    pw_hash = bcrypt.hashpw(b"the-right-one", bcrypt.gensalt(rounds=4)).decode()
    uid = admin.fetch_query(
        "INSERT INTO saas_users (username, email, password_hash, email_verified) "
        "VALUES (%s, %s, %s, TRUE) RETURNING id",
        (name, f"{name}@example.invalid", pw_hash))[0][0]
    barrier = threading.Barrier(8)
    errors: list[str] = []
    refused_locked: list[int] = []

    def worker() -> None:
        db = get_db_connection()
        try:
            barrier.wait(timeout=30)
            _user, reason = authenticate_api_user(db, name, "wrong")
            if reason == "locked":
                refused_locked.append(1)
        except Exception as exc:  # noqa: BLE001 — c'est l'objet de la mesure
            errors.append(repr(exc)[:200])
        finally:
            db.close()

    try:
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        assert not errors, errors
        count, locked = admin.fetch_query(
            "SELECT failed_login_attempts, locked_until IS NOT NULL "
            "FROM saas_users WHERE id = %s", (uid,))[0]
        # R400 (nuit du 2026-10-05, CI lente) : un fil qui lit le compte APRÈS le
        # verrou sort `locked` sans incrémenter — c'est le comportement voulu. Une mise
        # à jour PERDUE est un échec ni compté ni refusé : c'est ce total qu'on juge.
        assert count + len(refused_locked) == 8, (
            f"8 échecs simultanés : {count} comptés + {len(refused_locked)} refusés "
            "verrouillés ≠ 8 — une tentative s'est perdue, le seuil se contourne")
        assert locked, "8 échecs ≥ 5 et le compte n'est pas verrouillé"
    finally:
        admin.execute_query("DELETE FROM saas_users WHERE id = %s", (uid,))


class _RecordingDb:
    """Answers the login SELECT with one 2FA account; records every write."""

    def __init__(self, pw_hash: str) -> None:
        self.writes: list[str] = []
        self._row = (1, "u", "u@x", pw_hash, 1, "artist", True, 4, None, True, 0)

    def fetch_query(self, query, params=None):
        return [self._row]

    def execute_query(self, query, params=None):
        self.writes.append(" ".join(query.split()))


def test_a_correct_password_does_not_reset_the_2fa_counter_on_the_api() -> None:
    """R370 (audit) — the counter is SHARED with the TOTP codes. Resetting it on the
    password alone let 4 wrong codes + 1 API call repeat forever: no lockout ever."""
    from src.api.auth import authenticate_api_user, pwd_context

    db = _RecordingDb(pwd_context.hash("right-password"))
    user, reason = authenticate_api_user(db, "u", "right-password")
    assert (user, reason) == (None, "totp_required")
    assert not [w for w in db.writes if "failed_login_attempts = 0" in w], (
        f"a 2FA account's counter was reset by its password alone: {db.writes}")
