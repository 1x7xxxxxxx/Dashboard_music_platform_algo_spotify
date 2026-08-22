"""Deactivating an account, or changing its password, must end what is already open.

Installed 2026-08-22 (R24). Both gestures were writes that nothing read back:

  * `admin.py:_toggle_user_active` set `active = FALSE`, and `active` appeared in
    exactly one query — the LOGIN one. The holder kept the dashboard for as long as
    they kept clicking (idle timeout: 60 min) and the API for up to 24 h.
  * `account.py` replaced `password_hash`, and the JWT carried no reference to it.
    The one gesture every incident runbook prescribes evicted nobody.

What is pinned here is the READ side, on both surfaces. Writing `active = FALSE` is
easy to test and was never the problem.
"""
import uuid

import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()


@pytest.fixture
def account():
    """A live artist account, removed afterwards."""
    from src.dashboard.utils import get_db_connection
    from src.dashboard.views.register import _create_artist_and_user

    suffix = uuid.uuid4().hex[:10]
    db = get_db_connection()
    user_id, artist_id = _create_artist_and_user(
        db, artist_name=f"Revoke {suffix}", slug=f"revoke-{suffix}",
        username=f"revoke_{suffix}", email=f"{suffix}@example.test",
        pw="a-long-enough-password-1", token=f"tok-{suffix}",
    )
    db.execute_query("UPDATE saas_users SET email_verified = TRUE WHERE id = %s",
                     (user_id,))
    db.close()
    yield {"user_id": user_id, "artist_id": artist_id,
           "username": f"revoke_{suffix}", "password": "a-long-enough-password-1"}  # pragma: allowlist secret
    db = get_db_connection()
    db.execute_query("DELETE FROM saas_users WHERE id = %s", (user_id,))
    db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))
    db.close()


# ── the API half ────────────────────────────────────────────────────────────

def _api_client():
    pytest.importorskip("fastapi", reason="dev extras not installed")
    from fastapi.testclient import TestClient

    from src.api.main import app

    return TestClient(app)


def _token_for(account) -> str:
    from src.dashboard.utils import get_db_connection
    from src.api.auth import authenticate_api_user, create_access_token

    db = get_db_connection()
    user, reason = authenticate_api_user(db, account["username"], account["password"])
    db.close()
    assert user is not None, f"could not authenticate the fixture account: {reason}"
    return create_access_token({"sub": user["username"], "role": user["role"],
                                "artist_id": user["artist_id"],
                                "tv": user["token_version"]})


def test_a_live_token_works_before_anything_is_revoked(account):
    """Non-vacuity: without this, every assertion below could pass on a broken token."""
    r = _api_client().get("/artists/me",
                          headers={"Authorization": f"Bearer {_token_for(account)}"})
    assert r.status_code == 200, r.text


def test_deactivating_the_account_kills_its_api_token(account):
    from src.dashboard.utils import get_db_connection
    from src.dashboard.views.admin import _toggle_user_active

    token = _token_for(account)
    db = get_db_connection()
    _toggle_user_active(db, account["user_id"], False)
    db.close()

    r = _api_client().get("/artists/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401, (
        f"a deactivated account still reads its data: HTTP {r.status_code}. "
        "The token stays signature-valid for 24 h; only a re-read of the row can "
        "stop it."
    )


def test_changing_the_password_kills_tokens_issued_before_it(account):
    """The gesture after a compromise. It must evict the intruder, not just the hash."""
    from src.dashboard.utils import get_db_connection

    token = _token_for(account)
    db = get_db_connection()
    # What account.py:_section_password does, reduced to the two columns that matter.
    db.execute_query(
        "UPDATE saas_users SET password_hash = %s, token_version = token_version + 1 "
        "WHERE id = %s", ("$2b$12$" + "x" * 53, account["user_id"]),
    )
    db.close()

    r = _api_client().get("/artists/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401, (
        f"a token minted before the password change still works: HTTP {r.status_code}"
    )


def test_a_token_minted_before_migration_072_is_not_broken_by_it(account):
    """Deploying revocation must not sign out everyone holding a valid session.

    A pre-072 token carries no `tv` claim. Read as 0 against the column default of 0,
    it stays valid until it expires — which is what makes this deployable without a
    flag day.
    """
    from src.api.auth import create_access_token

    legacy = create_access_token({"sub": account["username"], "role": "artist",
                                  "artist_id": account["artist_id"]})
    r = _api_client().get("/artists/me", headers={"Authorization": f"Bearer {legacy}"})
    assert r.status_code == 200, (
        f"a token issued before 072 was rejected: HTTP {r.status_code} — {r.text}"
    )


def test_the_api_fails_closed_when_the_database_is_unreachable(account):
    """An outage must not be a window in which revocation does not apply."""
    from src.api.deps import get_db
    from src.api.main import app

    token = _token_for(account)
    app.dependency_overrides[get_db] = lambda: None
    try:
        r = _api_client().get("/artists/me",
                              headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 503, (
            f"HTTP {r.status_code} — with no database to ask, the only safe answer "
            "is 'cannot tell', not 'the signature checks out'"
        )
    finally:
        app.dependency_overrides.clear()


# ── the dashboard half ──────────────────────────────────────────────────────

def test_the_dashboard_re_reads_the_row_and_drops_a_revoked_session(account,
                                                                    monkeypatch):
    """`require_login()` trusted st.session_state alone. It must ask the database."""
    import streamlit as st

    from src.dashboard import auth as dash_auth
    from src.dashboard.utils import get_db_connection

    session = {
        "authenticated": True, "user_id": account["user_id"],
        "role": "artist", "artist_id": account["artist_id"],
        "_last_reauth_at": 0.0,
    }
    monkeypatch.setattr(st, "session_state", session, raising=False)
    monkeypatch.setattr(dash_auth.st, "session_state", session, raising=False)

    import time
    assert dash_auth._session_still_authorised(time.time()) is True, (
        "an active account was refused — the check is wrong in the other direction"
    )

    db = get_db_connection()
    db.execute_query("UPDATE saas_users SET active = FALSE WHERE id = %s",
                     (account["user_id"],))
    db.close()
    session["_last_reauth_at"] = 0.0  # past the re-read interval

    assert dash_auth._session_still_authorised(time.time()) is False, (
        "a deactivated account keeps its open dashboard session for as long as it "
        "keeps clicking"
    )


def test_a_role_change_takes_effect_without_a_logout(account, monkeypatch):
    """An admin demoted mid-session kept the admin menu until they left on their own."""
    import time

    import streamlit as st

    from src.dashboard import auth as dash_auth
    from src.dashboard.utils import get_db_connection

    db = get_db_connection()
    db.execute_query("UPDATE saas_users SET role = 'admin' WHERE id = %s",
                     (account["user_id"],))
    db.close()

    session = {"authenticated": True, "user_id": account["user_id"],
               "role": "artist", "artist_id": account["artist_id"],
               "_last_reauth_at": 0.0}
    monkeypatch.setattr(dash_auth.st, "session_state", session, raising=False)

    assert dash_auth._session_still_authorised(time.time()) is True
    assert session["role"] == "admin", (
        "the row said admin and the session still says artist — the re-read is not "
        "refreshing the claims it just read"
    )


def test_the_dashboard_fails_open_on_an_outage(account, monkeypatch):
    """Deliberate asymmetry with the API: a Postgres blip must not log out everyone."""
    import time

    from src.dashboard import auth as dash_auth

    session = {"authenticated": True, "user_id": account["user_id"],
               "role": "artist", "artist_id": account["artist_id"],
               "_last_reauth_at": 0.0}
    monkeypatch.setattr(dash_auth.st, "session_state", session, raising=False)
    monkeypatch.setattr(dash_auth, "_get_db", lambda: None)

    assert dash_auth._session_still_authorised(time.time()) is True
