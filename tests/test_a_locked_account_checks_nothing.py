"""A locked account checks nothing, and a secret that cannot be stored fails its task (R398).

Type: Guard
Uses: src.utils.login_lockout, src.api.auth, src.dashboard.auth, src.utils.credential_loader,
      src.utils.retry, src.collectors.soundcloud_api_collector
Depends on: live Postgres for the lockout tests (skipped without)
Persists in: throwaway accounts, deleted at the end

The three MEDIUM findings of the R370 security audit (2026-10-05):
  (a) `locked_until` was read with the user row, BEFORE bcrypt: a parallel burst all read
      « not locked » and all reached bcrypt — 4 + N tries per window;
  (b) the dashboard TOTP challenge never re-read `locked_until`: wrong codes locked the
      account, the same pending session kept submitting, the right code cleared the lock;
  (c) `update_platform_secret` returned None when it refused to write: a SoundCloud
      refresh_token (the old one revoked) was lost while the task stayed green.
"""
from __future__ import annotations

import os
import threading
import uuid

import pytest

from tests.db_gate import db_ready

_needs_db = pytest.mark.skipif(not db_ready(), reason="needs the provisioned DB")


@pytest.fixture
def account():
    """A verified password account with 2FA on — removed afterwards."""
    import bcrypt
    import pyotp

    from src.dashboard.utils import get_db_connection

    db = get_db_connection()
    name = f"lock-{uuid.uuid4().hex[:8]}"
    secret = pyotp.random_base32()
    uid = db.fetch_query(
        "INSERT INTO saas_users (username, email, password_hash, email_verified, "
        "totp_enabled, totp_secret) VALUES (%s, %s, %s, TRUE, TRUE, %s) RETURNING id",
        (name, f"{name}@example.invalid",
         bcrypt.hashpw(b"the-right-one", bcrypt.gensalt(rounds=4)).decode(), secret))[0][0]
    yield {"id": uid, "username": name, "secret": secret, "db": db}
    db.execute_query("DELETE FROM saas_users WHERE id = %s", (uid,))
    db.close()


def _state(db, uid: int) -> tuple[int, bool]:
    return db.fetch_query("SELECT failed_login_attempts, COALESCE(locked_until > NOW(), FALSE) "
                          "FROM saas_users WHERE id = %s", (uid,))[0]


@_needs_db
def test_a_parallel_burst_reaches_bcrypt_at_most_five_times(account, monkeypatch) -> None:
    import src.api.auth as api_auth
    from src.dashboard.utils import get_db_connection
    from src.utils.login_lockout import MAX_LOGIN_ATTEMPTS

    account["db"].execute_query("UPDATE saas_users SET totp_enabled = FALSE WHERE id = %s",
                                (account["id"],))
    checks: list[int] = []
    lock = threading.Lock()
    real = api_auth.verify_password

    def counted(plain, hashed):
        with lock:
            checks.append(1)
        return real(plain, hashed)

    monkeypatch.setattr(api_auth, "verify_password", counted)
    barrier = threading.Barrier(12)
    errors: list[str] = []

    def worker() -> None:
        db = get_db_connection()
        try:
            barrier.wait(timeout=30)
            api_auth.authenticate_api_user(db, account["username"], "wrong")
        except Exception as exc:  # noqa: BLE001 — the measurement itself
            errors.append(repr(exc)[:200])
        finally:
            db.close()

    threads = [threading.Thread(target=worker) for _ in range(12)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert not errors, errors
    assert len(checks) <= MAX_LOGIN_ATTEMPTS, (
        f"12 simultaneous wrong passwords ran bcrypt {len(checks)} times — the lock read "
        f"before the check let the burst through (at most {MAX_LOGIN_ATTEMPTS})")
    assert _state(account["db"], account["id"]) == (MAX_LOGIN_ATTEMPTS, True)


@_needs_db
def test_an_expired_lock_lets_the_right_password_in(account) -> None:
    from src.dashboard import auth as dash_auth

    db = account["db"]
    db.execute_query("UPDATE saas_users SET failed_login_attempts = 5, "
                     "locked_until = NOW() - INTERVAL '1 minute' WHERE id = %s",
                     (account["id"],))
    user, err = dash_auth._authenticate_user(account["username"], "the-right-one", db)
    assert user is not None, f"the lock had expired and the right password was refused: {err}"
    assert _state(db, account["id"]) == (1, False), (
        "an expired lock did not open a fresh window — the old count relocked the account")


_CHALLENGE = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
from src.dashboard import auth as dash_auth
from src.dashboard.utils import get_db_connection
if "_started" not in st.session_state:
    st.session_state["_started"] = True
    st.session_state["_totp_pending"] = {pending!r}
db = get_db_connection()
try:
    dash_auth._show_totp_challenge(db)
finally:
    db.close()
"""


@_needs_db
def test_the_right_code_on_a_locked_account_does_not_log_in(account) -> None:
    import pyotp
    from streamlit.testing.v1 import AppTest

    db = account["db"]
    db.execute_query("UPDATE saas_users SET failed_login_attempts = 5, "
                     "locked_until = NOW() + INTERVAL '10 minutes' WHERE id = %s",
                     (account["id"],))
    pending = {"id": account["id"], "username": account["username"], "email": "x@x",
               "artist_id": None, "role": "artist", "totp_secret": account["secret"]}
    at = AppTest.from_string(_CHALLENGE.format(root=os.getcwd(), pending=pending))
    at.run(timeout=60)
    at.text_input[0].input(pyotp.TOTP(account["secret"]).now())
    next(b for b in at.button if b.label == "Vérifier").click().run(timeout=60)
    assert not at.exception, at.exception
    assert not at.session_state["authenticated"] if "authenticated" in at.session_state \
        else True, "the right code logged into a locked account"
    assert _state(db, account["id"]) == (5, True), (
        "the right code cleared the lock on a locked account")
    assert any("verrouillé" in e.value for e in at.error), [e.value for e in at.error]


def test_a_secret_that_cannot_be_stored_raises(monkeypatch) -> None:
    from src.utils.credential_loader import SecretNotPersistedError, update_platform_secret

    monkeypatch.delenv("FERNET_KEY", raising=False)
    with pytest.raises(SecretNotPersistedError):
        update_platform_secret(1, "soundcloud", "refresh_token", "new")


def test_a_lost_refresh_token_is_not_retried_into_a_green_run(monkeypatch) -> None:
    """The rotated token lives in memory: a retry would succeed on it and hide the loss."""
    import src.utils.credential_loader as cl
    from src.collectors.soundcloud_api_collector import SoundCloudCollector
    from src.utils.retry import retry

    def refuse(*_a, **_k):
        raise cl.SecretNotPersistedError("refused")

    monkeypatch.setattr(cl, "update_platform_secret", refuse)
    monkeypatch.setattr("src.utils.instance_identity.is_production", lambda: True)

    class _Reply:
        status_code = 200

        @staticmethod
        def json():
            return {"access_token": "a", "expires_in": 3600, "refresh_token": "rotated"}

    collector = object.__new__(SoundCloudCollector)
    collector.artist_id, collector.client_id, collector.client_secret = 1, "c", "s"
    collector.refresh_token = "old"
    collector.session = type("S", (), {"post": staticmethod(lambda *a, **k: _Reply())})()
    calls: list[int] = []

    @retry(max_attempts=3, base_delay=0)
    def collect():
        calls.append(1)
        collector._get_user_token()

    with pytest.raises(cl.SecretNotPersistedError):
        collect()
    assert calls == [1], f"a lost secret was retried {len(calls)} times"
