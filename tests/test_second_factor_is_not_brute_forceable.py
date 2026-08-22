"""A wrong TOTP code must cost something that a new browser tab cannot refund.

Installed 2026-08-22 (R26). The challenge in `auth.py:_show_totp_challenge` looked
rate-limited and was not, for two independent reasons that had to be fixed together:

  * the only counter it touched was `_rate_record_failure()`, which lives in
    `st.session_state` — one browser tab. The attacker knows the password (that is
    the premise of a second factor), so opening a fresh tab and resubmitting it
    reforged `_totp_pending` with a clean budget, at the cost of one request;
  * `failed_login_attempts`, the counter that DOES survive a new session, was reset
    to 0 by `_authenticate_user` the moment the password verified — before the code
    was ever asked for. So the account-level lockout could never fire on 2FA either.

With `valid_window=1` three codes out of 10^6 are live at any instant. Unlimited
attempts turns that into a matter of hours.
"""
import time
import uuid

import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()


@pytest.fixture
def totp_account():
    """An account with 2FA on, removed afterwards."""
    import pyotp

    from src.dashboard.utils import get_db_connection
    from src.dashboard.views.register import _create_artist_and_user

    suffix = uuid.uuid4().hex[:10]
    secret = pyotp.random_base32()
    db = get_db_connection()
    user_id, artist_id = _create_artist_and_user(
        db, artist_name=f"Totp {suffix}", slug=f"totp-{suffix}",
        username=f"totp_{suffix}", email=f"{suffix}@example.test",
        pw="a-long-enough-password-1", token=f"tok-{suffix}",
    )
    db.execute_query(
        "UPDATE saas_users SET email_verified = TRUE, totp_enabled = TRUE, "
        "totp_secret = %s WHERE id = %s", (secret, user_id),
    )
    db.close()
    yield {"user_id": user_id, "artist_id": artist_id, "secret": secret,
           "username": f"totp_{suffix}", "password": "a-long-enough-password-1"}  # pragma: allowlist secret
    db = get_db_connection()
    db.execute_query("DELETE FROM saas_users WHERE id = %s", (user_id,))
    db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))
    db.close()


def _failed_attempts(user_id: int) -> int:
    from src.dashboard.utils import get_db_connection

    db = get_db_connection()
    n = db.fetch_query(
        "SELECT failed_login_attempts FROM saas_users WHERE id = %s", (user_id,)
    )[0][0]
    db.close()
    return n


def test_the_password_does_not_refund_the_lockout_budget_when_2fa_is_owed(totp_account,
                                                                          monkeypatch):
    """The reset must wait for the LAST factor, not the first one.

    This is the subtle half. Nothing about the reset looked wrong in isolation — it
    is exactly what a password-only login should do. It was wrong only because a
    second factor came after it.
    """
    import streamlit as st

    from src.dashboard import auth as dash_auth
    from src.dashboard.utils import get_db_connection

    monkeypatch.setattr(dash_auth.st, "session_state", {}, raising=False)
    monkeypatch.setattr(st, "session_state", {}, raising=False)

    db = get_db_connection()
    db.execute_query("UPDATE saas_users SET failed_login_attempts = 3 WHERE id = %s",
                     (totp_account["user_id"],))
    user, err = dash_auth._authenticate_user(
        totp_account["username"], totp_account["password"], db
    )
    db.close()

    assert user is not None and user["totp_enabled"], f"password step failed: {err}"
    assert _failed_attempts(totp_account["user_id"]) == 3, (
        "the correct password zeroed the account's failure counter while a second "
        "factor was still owed — every wrong code could then be followed by one "
        "cheap re-login to clear the slate"
    )


def test_a_wrong_code_counts_against_the_account_not_just_the_tab(totp_account):
    """The counter that a new browser session cannot reset must move."""
    from src.dashboard import auth as dash_auth
    from src.dashboard.utils import get_db_connection

    before = _failed_attempts(totp_account["user_id"])
    db = get_db_connection()
    dash_auth._record_second_factor_failure(db, totp_account["username"])
    db.close()

    assert _failed_attempts(totp_account["user_id"]) == before + 1, (
        "a wrong second factor left no trace in the database, so the 5-attempt "
        "lockout could never fire on it"
    )


def test_enough_wrong_codes_lock_the_account(totp_account):
    from src.dashboard import auth as dash_auth
    from src.dashboard.utils import get_db_connection

    db = get_db_connection()
    for _ in range(dash_auth._MAX_LOGIN_ATTEMPTS):
        dash_auth._record_second_factor_failure(db, totp_account["username"])
    locked = db.fetch_query(
        "SELECT locked_until FROM saas_users WHERE id = %s",
        (totp_account["user_id"],),
    )[0][0]
    db.close()

    assert locked is not None, (
        f"{dash_auth._MAX_LOGIN_ATTEMPTS} wrong codes did not lock the account"
    )


def test_the_totp_budget_survives_a_brand_new_session():
    """The property the session-state counter never had.

    `_rate_record_failure` stores in `st.session_state`; this asserts the replacement
    does not, by clearing the session between every attempt — which is precisely the
    attacker's move.
    """
    import streamlit as st

    from src.dashboard.utils import throttle

    for lim in throttle._LIMITERS.values():
        lim._hits.clear()
    try:
        for _ in range(throttle.TOTP_MAX):
            st.session_state.clear() if hasattr(st, "session_state") else None
            assert throttle.throttle_check("totp") is None
            throttle.throttle_record("totp")

        assert throttle.throttle_check("totp") is not None, (
            f"attempt #{throttle.TOTP_MAX + 1} was allowed after clearing the session "
            "between each one — the budget is still per-tab, which is no budget"
        )
    finally:
        for lim in throttle._LIMITERS.values():
            lim._hits.clear()


def test_the_budget_is_a_sliding_window_not_a_permanent_ban():
    """A locked-out honest user must get back in without an admin."""
    from src.utils.request_throttle import SlidingWindowLimiter

    lim = SlidingWindowLimiter(2, 60)
    t0 = time.time()
    assert lim.hit("k", now=t0) is None
    assert lim.hit("k", now=t0 + 1) is None
    assert lim.hit("k", now=t0 + 2) is not None
    assert lim.hit("k", now=t0 + 61) is None, (
        "the window never slid — one burst would bar that client forever"
    )
