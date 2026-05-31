"""Auth module — DB-based authentication (Brick 2).

Type: Core
Depends on: saas_users table, saas_artists table, get_db_connection
Persists in: PostgreSQL spotify_etl (saas_users)

User records are stored in saas_users. Passwords are bcrypt-hashed via passlib.
artist_id = NULL in saas_users means admin (unrestricted cross-tenant access).

Registration: GET /?page=register — accessible without login.
Bootstrap:    if saas_users is empty, first-run admin creation form is shown.
"""
import re
import sys
import time
from pathlib import Path
from typing import Optional

import bcrypt
import streamlit as st

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


_SESSION_KEYS = ['authenticated', 'username', 'name', 'artist_id', 'role', 'user_id']

# Brick 26: session-based rate limit (no reliable IP in Streamlit without reverse proxy)
_RATE_MAX_ATTEMPTS = 10   # failures per session window
_RATE_WINDOW_SECS  = 300  # 5-minute sliding window


def _check_session_rate_limit() -> bool:
    """Return False and display error if current session exceeds login rate limit."""
    now = time.time()
    window_start = st.session_state.get('_rate_window_start', now)
    attempts = st.session_state.get('_rate_attempts', 0)

    if now - window_start > _RATE_WINDOW_SECS:
        st.session_state['_rate_window_start'] = now
        st.session_state['_rate_attempts'] = 0
        return True

    if attempts >= _RATE_MAX_ATTEMPTS:
        remaining = int(_RATE_WINDOW_SECS - (now - window_start))
        st.error(f"Too many failed attempts. Please wait {remaining} seconds before trying again.")
        return False
    return True


def _rate_record_failure():
    now = time.time()
    if 'rate_window_start' not in st.session_state:
        st.session_state['_rate_window_start'] = now
    st.session_state['_rate_attempts'] = st.session_state.get('_rate_attempts', 0) + 1


def _rate_reset():
    st.session_state.pop('_rate_attempts', None)
    st.session_state.pop('_rate_window_start', None)


# ─────────────────────────────────────────────
# Password helpers
# ─────────────────────────────────────────────

_PW_RE = re.compile(r'^(?=.*[A-Za-z])(?=.*\d).{10,}$')


def _validate_password_strength(pw: str) -> Optional[str]:
    """Return an error string if the password is too weak, else None.

    HIGH-04: minimum 10 characters with at least one letter and one digit.
    """
    if not _PW_RE.fullmatch(pw):
        return "Password must be at least 10 characters and contain at least one letter and one digit."
    return None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


# ─────────────────────────────────────────────
# DB helpers (auth-specific, avoid circular import)
# ─────────────────────────────────────────────

def _get_db():
    from src.dashboard.utils import get_db_connection
    return get_db_connection()


# Brick 32 — heartbeat throttle. With TTL=5 min on active_sessions, 60 s gives
# ~5 heartbeats per liveness window: enough redundancy if one INSERT drops.
_HEARTBEAT_THROTTLE_SECS = 60


def _maybe_bump_heartbeat() -> None:
    """Refresh active_sessions for the current artist, ≤1 write / 60 s / session.

    Skips admins (artist_id is None) — admins are not counted as "live artists".
    Fire-and-forget: any DB failure is logged inside bump_heartbeat and ignored.
    """
    artist_id = st.session_state.get('artist_id')
    if artist_id is None:
        return
    last = st.session_state.get('_last_heartbeat_at', 0.0)
    now = time.time()
    if now - last <= _HEARTBEAT_THROTTLE_SECS:
        return
    from src.dashboard.utils.live_pulse import bump_heartbeat
    db = _get_db()
    if db is None:
        return
    try:
        bump_heartbeat(db, artist_id)
        st.session_state['_last_heartbeat_at'] = now
    finally:
        db.close()


def _user_table_empty(db) -> bool:
    rows = db.fetch_query("SELECT 1 FROM saas_users LIMIT 1")
    return len(rows) == 0


_MAX_LOGIN_ATTEMPTS = 5
_LOCKOUT_MINUTES    = 15


def _authenticate_user(username: str, password: str, db) -> tuple[Optional[dict], Optional[str]]:
    """Return (user_dict, None) on success, (None, error_msg) on failure.

    HIGH-01: Enforces brute-force lockout — 5 consecutive failures → locked for 15 min.
    HIGH-02: Never discloses the email address on unverified-account error.
    """
    from datetime import datetime, timezone
    rows = db.fetch_query(
        "SELECT id, username, email, password_hash, artist_id, role, email_verified, "
        "       failed_login_attempts, locked_until, totp_enabled, totp_secret "
        "FROM saas_users WHERE username = %s AND active = TRUE LIMIT 1",
        (username.strip(),)
    )
    if not rows:
        return None, "Invalid username or password."

    uid, uname, email, pw_hash, artist_id, role, email_verified, fail_count, locked_until, totp_enabled, totp_secret = rows[0]

    # HIGH-01: check lockout before bcrypt (prevents timing oracle on locked accounts)
    if locked_until:
        now = datetime.now(timezone.utc)
        locked_until_aware = locked_until if locked_until.tzinfo else locked_until.replace(tzinfo=timezone.utc)
        if now < locked_until_aware:
            remaining = int((locked_until_aware - now).total_seconds() // 60) + 1
            return None, f"Account locked after too many failed attempts. Try again in {remaining} minute(s)."

    if not verify_password(password, pw_hash):
        # Increment failure counter; lock if threshold reached
        new_fail = (fail_count or 0) + 1
        if new_fail >= _MAX_LOGIN_ATTEMPTS:
            db.execute_query(
                "UPDATE saas_users SET failed_login_attempts = %s, "
                "locked_until = NOW() + INTERVAL '%s minutes' WHERE id = %s",
                (new_fail, _LOCKOUT_MINUTES, uid)
            )
        else:
            db.execute_query(
                "UPDATE saas_users SET failed_login_attempts = %s WHERE id = %s",
                (new_fail, uid)
            )
        return None, "Invalid username or password."

    # Successful authentication — reset failure counter
    db.execute_query(
        "UPDATE saas_users SET failed_login_attempts = 0, locked_until = NULL WHERE id = %s",
        (uid,)
    )

    if not email_verified:
        # HIGH-02: do NOT expose the email address in the error string
        return None, "__unverified__"

    return {"id": uid, "username": uname, "email": email,
            "artist_id": artist_id, "role": role,
            "totp_enabled": bool(totp_enabled), "totp_secret": totp_secret}, None


def _resend_verification(username: str, email: str, db) -> None:
    import secrets
    from src.utils.verification_email import send_verification_email
    token = secrets.token_urlsafe(32)
    db.execute_query(
        "UPDATE saas_users SET verification_token = %s WHERE username = %s",
        (token, username)
    )
    if send_verification_email(email, username, token):
        st.success(f"Verification email resent to {email}.")
    else:
        st.error("Failed to send email. Check SMTP config in config/config.yaml.")


def _hydrate_session(user: dict) -> None:
    st.session_state['authenticated'] = True
    st.session_state['username']      = user['username']
    st.session_state['name']          = user['email']
    st.session_state['artist_id']     = user['artist_id']  # None = admin
    st.session_state['role']          = user['role']
    st.session_state['user_id']       = user['id']


# ─────────────────────────────────────────────
# TOTP 2FA challenge (Brick 28)
# ─────────────────────────────────────────────

def _show_totp_challenge(db) -> None:
    """Render the TOTP verification step after password auth succeeds."""
    pending = st.session_state.get('_totp_pending')
    if not pending:
        return

    st.title("🎵 Music Dashboard")
    st.subheader("🔐 Two-factor authentication")
    st.info(f"Signed in as **{pending['username']}**. Enter the 6-digit code from your authenticator app.")

    with st.form("totp_challenge"):
        code = st.text_input("Authentication code", max_chars=6, placeholder="000000")
        col1, col2 = st.columns(2)
        submitted = col1.form_submit_button("Verify", type="primary")
        cancel    = col2.form_submit_button("Cancel")

    if cancel:
        st.session_state.pop('_totp_pending', None)
        st.rerun()

    if submitted:
        try:
            import pyotp
            totp = pyotp.TOTP(pending['totp_secret'])
            if totp.verify(code.strip(), valid_window=1):
                user = dict(pending)
                st.session_state.pop('_totp_pending', None)
                _rate_reset()
                st.session_state.clear()
                _hydrate_session(user)
                db.execute_query(
                    "UPDATE saas_users SET updated_at = NOW() WHERE username = %s",
                    (user['username'],)
                )
                st.rerun()
            else:
                _rate_record_failure()
                st.error("Invalid authentication code. Please try again.")
        except ImportError:
            st.error("pyotp not installed. Run: pip install pyotp")


# ─────────────────────────────────────────────
# Bootstrap (first-run admin creation)
# ─────────────────────────────────────────────

def _show_bootstrap_form(db) -> None:
    st.title("🎵 Music Dashboard — First-time setup")
    st.warning(
        "No users found in the database. Create the first **admin** account to get started.",
        icon="⚠️",
    )
    with st.form("bootstrap_admin"):
        st.subheader("Create admin account")
        username = st.text_input("Username")
        email    = st.text_input("Email")
        pw       = st.text_input("Password", type="password")
        pw2      = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create admin", type="primary")

    if submitted:
        if not username or not email or not pw:
            st.error("All fields are required.")
            return
        if pw != pw2:
            st.error("Passwords do not match.")
            return
        pw_error = _validate_password_strength(pw)
        if pw_error:
            st.error(pw_error)
            return
        try:
            db.execute_query(
                """
                INSERT INTO saas_users
                    (username, email, password_hash, artist_id, role, email_verified)
                VALUES (%s, %s, %s, NULL, 'admin', TRUE)
                """,
                (username.strip(), email.strip(), hash_password(pw))
            )
            st.success(f"Admin account '{username}' created. You can now log in.")
            st.rerun()
        except Exception as e:
            st.error(f"Error creating admin: {e}")


# ─────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────

def require_login() -> bool:
    """Show login form if not authenticated.

    Stores in st.session_state:
        authenticated (bool)
        username      (str)
        name          (str)   — email used as display name
        artist_id     (int | None) — None = admin
        role          (str)   — 'admin' | 'artist'

    Returns True if authenticated, False otherwise.
    """
    if st.session_state.get('authenticated'):
        _maybe_bump_heartbeat()
        return True

    db = _get_db()
    if db is None:
        st.error("❌ Database unreachable. Make sure Docker is running: `docker-compose up -d`")
        return False

    try:
        if _user_table_empty(db):
            _show_bootstrap_form(db)
            return False

        # Brick 28: TOTP challenge takes priority over the login form
        if st.session_state.get('_totp_pending'):
            _show_totp_challenge(db)
            return False

        st.title("🎵 streaMLytics")

        with st.form("login"):
            st.subheader("Sign in")
            username  = st.text_input("Username")
            password  = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary")

        st.markdown("[Don't have an account? **Create one**](?page=register)")
        st.caption("🔒 Votre mot de passe est chiffré (bcrypt) et n'est jamais stocké en clair — conformément au RGPD.")

        if submitted:
            if not username or not password:
                st.error("Please enter your username and password.")
                return False

            # Brick 26: session-based rate limit check
            if not _check_session_rate_limit():
                return False

            user, error = _authenticate_user(username, password, db)
            if user:
                _rate_reset()
                if user.get('totp_enabled'):
                    # Brick 28: password OK but TOTP required — defer full hydration
                    st.session_state['_totp_pending'] = user
                    st.rerun()
                    return False
                # MEDIUM-01: clear pre-auth session state before hydrating
                st.session_state.clear()
                _hydrate_session(user)
                db.execute_query(
                    "UPDATE saas_users SET updated_at = NOW() WHERE username = %s",
                    (username,)
                )
                st.rerun()
                return True
            _rate_record_failure()
            if error and error == "__unverified__":
                # HIGH-02: do not disclose the email address
                st.warning(
                    "📧 Please verify your email address before signing in. "
                    "Check the inbox you registered with."
                )
                if st.button("Resend verification email"):
                    # Look up email separately only after the user explicitly requests it
                    rows = db.fetch_query(
                        "SELECT email FROM saas_users WHERE username = %s AND active = TRUE LIMIT 1",
                        (username.strip(),)
                    )
                    if rows:
                        _resend_verification(username, rows[0][0], db)
            else:
                st.error(error or "Invalid username or password.")
        return False

    finally:
        db.close()


# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────

def show_user_sidebar():
    """Show username, role, and logout button in sidebar."""
    name      = st.session_state.get('name', '')
    role      = st.session_state.get('role', 'artist')
    artist_id = st.session_state.get('artist_id')

    role_label = '👑 Admin' if role == 'admin' else '🎤 Artist'
    st.sidebar.markdown(f"**{role_label}** — {name}")
    if artist_id is not None:
        st.sidebar.caption(f"artist_id = {artist_id}")
    else:
        st.sidebar.caption("Global access (all artists)")

    if st.sidebar.button('Logout'):
        for key in _SESSION_KEYS:
            st.session_state.pop(key, None)
        st.rerun()


# ─────────────────────────────────────────────
# Session helpers (unchanged API)
# ─────────────────────────────────────────────

def get_artist_id() -> Optional[int]:
    """Return artist_id from session (None = admin, sees all data).

    Default is None — not 1. Callers that need a non-None fallback must
    handle the None case explicitly (e.g. guard with is_admin() check).
    """
    return st.session_state.get('artist_id')


def is_admin() -> bool:
    return st.session_state.get('role') == 'admin'


def get_artist_plan() -> str:
    """Return the current artist's plan: 'free' | 'basic' | 'premium'.

    Reads artist_subscriptions from DB; falls back to saas_artists.tier.
    Returns 'premium' for admin sessions (unrestricted access).
    """
    if is_admin():
        return 'premium'

    artist_id = get_artist_id()
    if artist_id is None:
        return 'premium'

    try:
        from src.dashboard.utils import get_db_connection
        from datetime import datetime, timezone
        db = get_db_connection()
        if db is None:
            return 'free'

        # Single query: promo state + subscription plan + tier fallback
        row = db.fetch_query(
            """
            SELECT
                sa.promo_plan,
                sa.promo_plan_expires_at,
                sp.name        AS subscription_plan,
                sa.tier
            FROM saas_artists sa
            LEFT JOIN artist_subscriptions asub
                ON asub.artist_id = sa.id
                AND asub.status IN ('active', 'trialing')
            LEFT JOIN subscription_plans sp ON sp.id = asub.plan_id
            WHERE sa.id = %s
            LIMIT 1
            """,
            (artist_id,),
        )
        db.close()

        if not row:
            return 'free'

        promo_plan, promo_expires, subscription_plan, tier = row[0]

        # Promo takes precedence if still active
        if promo_plan and (promo_expires is None or promo_expires > datetime.now(timezone.utc)):
            return promo_plan

        # Active Stripe subscription
        if subscription_plan:
            return subscription_plan

        # Legacy tier fallback
        if tier:
            return tier

    except Exception:
        pass
    return 'free'


def require_plan(min_plan: str) -> bool:
    """Show a paywall banner if the artist's plan is below min_plan.

    Returns True if access is allowed, False if blocked.
    """
    from src.database.stripe_schema import PLAN_RANK
    current_plan = get_artist_plan()
    if PLAN_RANK.get(current_plan, 0) >= PLAN_RANK.get(min_plan, 0):
        return True

    plan_labels = {'basic': 'Basic (9.90€/mo)', 'premium': 'Premium (29.90€/mo)'}
    st.warning(
        f"🔒 This feature requires the **{plan_labels.get(min_plan, min_plan)}** plan. "
        f"Your current plan: **{current_plan}**.",
        icon="⚠️",
    )
    if st.button("→ Voir les plans et upgrader", key=f"_upgrade_btn_{min_plan}"):
        st.query_params["page"] = "upgrade"
        st.rerun()
    # MEDIUM-02: st.stop() ensures the calling view never renders gated content,
    # even if the caller forgets to check the return value.
    st.stop()


def artist_id_sql_filter(table_alias: str = '') -> tuple:
    """Return (sql_fragment, params) to filter queries by artist_id.

    Returns ('', ()) for admin (no filter — sees all data).
    Returns ('AND [alias.]artist_id = %s', (id,)) for artist sessions.

    CRITICAL-03: table_alias is validated against an identifier allowlist to
    prevent SQL injection when the fragment is interpolated into f-string queries.
    """
    _ALIAS_RE = re.compile(r'^[a-z_][a-z0-9_]*$')
    if table_alias and not _ALIAS_RE.match(table_alias):
        raise ValueError(f"artist_id_sql_filter: invalid table_alias '{table_alias}'")

    artist_id = get_artist_id()
    if artist_id is None:
        return "", ()
    prefix = f"{table_alias}." if table_alias else ""
    return f"AND {prefix}artist_id = %s", (artist_id,)
