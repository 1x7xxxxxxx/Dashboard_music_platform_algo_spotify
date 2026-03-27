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
from pathlib import Path
from typing import Optional

import bcrypt
import streamlit as st

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.utils.config_loader import config_loader

_SESSION_KEYS = ['authenticated', 'username', 'name', 'artist_id', 'role']


# ─────────────────────────────────────────────
# Password helpers
# ─────────────────────────────────────────────

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


def _user_table_empty(db) -> bool:
    rows = db.fetch_query("SELECT 1 FROM saas_users LIMIT 1")
    return len(rows) == 0


def _authenticate_user(username: str, password: str, db) -> tuple[Optional[dict], Optional[str]]:
    """Return (user_dict, None) on success, (None, error_msg) on failure."""
    rows = db.fetch_query(
        "SELECT id, username, email, password_hash, artist_id, role, email_verified "
        "FROM saas_users WHERE username = %s AND active = TRUE LIMIT 1",
        (username.strip(),)
    )
    if not rows:
        return None, "Invalid username or password."
    uid, uname, email, pw_hash, artist_id, role, email_verified = rows[0]
    if not verify_password(password, pw_hash):
        return None, "Invalid username or password."
    if not email_verified:
        return None, f"__unverified__{email}"
    return {"id": uid, "username": uname, "email": email,
            "artist_id": artist_id, "role": role}, None


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
        if len(pw) < 8:
            st.error("Password must be at least 8 characters.")
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
        return True

    db = _get_db()
    if db is None:
        st.error("❌ Database unreachable. Make sure Docker is running: `docker-compose up -d`")
        return False

    try:
        if _user_table_empty(db):
            _show_bootstrap_form(db)
            return False

        st.title("🎵 Music Dashboard")

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
            user, error = _authenticate_user(username, password, db)
            if user:
                _hydrate_session(user)
                db.execute_query(
                    "UPDATE saas_users SET updated_at = NOW() WHERE username = %s",
                    (username,)
                )
                st.rerun()
                return True
            if error and error.startswith("__unverified__"):
                email = error.replace("__unverified__", "")
                st.warning(
                    f"📧 Please verify your email address before signing in. "
                    f"Check your inbox at **{email}**."
                )
                if st.button("Resend verification email"):
                    _resend_verification(username, email, db)
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
    """Return artist_id from session (None = admin, sees all data)."""
    return st.session_state.get('artist_id', 1)


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
        db = get_db_connection()
        if db is None:
            return 'free'
        row = db.fetch_query(
            """
            SELECT sp.name
            FROM artist_subscriptions asub
            JOIN subscription_plans sp ON sp.id = asub.plan_id
            WHERE asub.artist_id = %s AND asub.status IN ('active', 'trialing')
            LIMIT 1
            """,
            (artist_id,),
        )
        db.close()
        if row:
            return row[0][0]
        db2 = get_db_connection()
        tier_row = db2.fetch_query(
            "SELECT tier FROM saas_artists WHERE id = %s", (artist_id,)
        )
        db2.close()
        if tier_row:
            return tier_row[0][0]
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
        f"Your current plan: **{current_plan}**. Upgrade via the **Billing** page.",
        icon="⚠️",
    )
    return False


def artist_id_sql_filter(table_alias: str = '') -> tuple:
    """Return (sql_fragment, params) to filter queries by artist_id.

    Returns ('', ()) for admin (no filter — sees all data).
    Returns ('AND artist_id = %s', (id,)) for artist sessions.
    """
    artist_id = get_artist_id()
    if artist_id is None:
        return "", ()
    prefix = f"{table_alias}." if table_alias else ""
    return f"AND {prefix}artist_id = %s", (artist_id,)
