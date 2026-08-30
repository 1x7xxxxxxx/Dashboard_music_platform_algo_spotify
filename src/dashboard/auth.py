"""Auth module — DB-based authentication (Brick 2).

Type: Core
Depends on: saas_users table, saas_artists table, get_db_connection
Persists in: PostgreSQL spotify_etl (saas_users)

User records are stored in saas_users. Passwords are bcrypt-hashed via passlib.
artist_id = NULL in saas_users means admin (unrestricted cross-tenant access).

Registration: GET /?page=register — accessible without login.
Bootstrap:    if saas_users is empty, first-run admin creation form is shown.
"""
import os
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


# The keys a hydrated session carries. Documentary since 2026-08-22: logout calls
# st.session_state.clear() instead of popping this list, because the list was six
# names and the session holds more — `_totp_pending` (which carries `totp_secret`)
# survived a logout. Kept because it names the contract `_hydrate_session` fills;
# do NOT reintroduce a pop-loop over it.
_SESSION_KEYS = ['authenticated', 'username', 'name', 'artist_id', 'role', 'user_id']


def _t(key: str, default: str) -> str:
    """Deferred i18n lookup. utils/__init__ imports this module back
    (get_artist_id), so importing i18n at module load time would be circular —
    the import happens at render time only."""
    from src.dashboard.utils.i18n import t
    return t(key, default)

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
        st.error(_t("auth.rate_limited",
                    "Trop de tentatives échouées. Réessayez dans {s} secondes.").format(s=remaining))
        return False
    return True


def _rate_record_failure():
    now = time.time()
    # The key is `_rate_window_start`, with the underscore. Testing for the name
    # WITHOUT it (the shape until 2026-08-22) meant the condition was always true,
    # so every failure restarted the window and the counter never reached its cap.
    # It failed closed — the budget was simply never spent — but the code did not do
    # what reading it says it does, and the R26 fix relies on this one being honest.
    if '_rate_window_start' not in st.session_state:
        st.session_state['_rate_window_start'] = now
    st.session_state['_rate_attempts'] = st.session_state.get('_rate_attempts', 0) + 1


def _rate_reset():
    st.session_state.pop('_rate_attempts', None)
    st.session_state.pop('_rate_window_start', None)


# C3 hardening: idle-session timeout — an authenticated tab left unattended
# expires server-side instead of staying valid until the process restarts.
_IDLE_TIMEOUT_SECS = int(os.getenv('SESSION_IDLE_TIMEOUT_MINUTES', '60')) * 60


def _session_idle_expired(last_activity: Optional[float], now: float,
                          timeout_secs: int = _IDLE_TIMEOUT_SECS) -> bool:
    """True when the gap since the last interaction exceeds the idle timeout."""
    return last_activity is not None and (now - last_activity) > timeout_secs


# How long an authenticated session may go without re-reading its own row.
# Not zero: Streamlit reruns the whole script on every widget interaction, and a
# connection per click for a page that already opens one is a real cost. Not long
# either: this interval IS the revocation delay an admin gets after clicking
# "désactiver", so it has to be a number you would say out loud in an incident.
_REAUTH_INTERVAL_SECS = int(os.getenv('SESSION_REAUTH_INTERVAL_SECS', '30'))


def _session_still_authorised(now: float) -> bool:
    """Re-read this session's own row and answer whether it may continue.

    R24, 2026-08-22. `require_login()` used to trust `st.session_state` alone, so the
    three columns that decide authorisation — `active`, `role`, `artist_id` — were
    read exactly once, at login. Deactivating an account did not end its session;
    neither did changing its password after a compromise. The holder kept the
    dashboard for as long as they kept clicking.

    Also refreshes `role` and `artist_id` from the row: an admin demoted mid-session
    kept the admin menu until they logged out on their own.

    Fails OPEN on a database outage, and this is the one deliberate asymmetry with
    the API's `get_current_user` (which 503s): a Postgres blip must not log out every
    artist mid-session, and the dashboard already shows a red banner in that state.
    The API has no such banner and its tokens travel further, so it fails closed.
    """
    last = st.session_state.get('_last_reauth_at', 0.0)
    if now - last < _REAUTH_INTERVAL_SECS:
        return True
    user_id = st.session_state.get('user_id')
    if user_id is None:
        return True  # bootstrap/legacy session with no id — nothing to look up
    db = _get_db()
    if db is None:
        return True  # outage: see docstring
    try:
        rows = db.fetch_query(
            "SELECT active, role, artist_id FROM saas_users WHERE id = %s", (user_id,)
        )
    finally:
        db.close()
    if not rows:
        return False  # the account was deleted under this session
    active, role, artist_id = rows[0]
    if not active:
        return False
    st.session_state['role'] = role
    st.session_state['artist_id'] = artist_id
    st.session_state['_last_reauth_at'] = now
    return True


# ─────────────────────────────────────────────
# Password helpers
# ─────────────────────────────────────────────

_PW_RE = re.compile(r'^(?=.*[A-Za-z])(?=.*\d).{10,}$')


def _validate_password_strength(pw: str) -> Optional[str]:
    """Return an error string if the password is too weak, else None.

    HIGH-04: minimum 10 characters with at least one letter and one digit.
    """
    if not _PW_RE.fullmatch(pw):
        return _t("auth.pw_policy",
                  "Le mot de passe doit contenir au moins 10 caractères, dont au moins "
                  "une lettre et un chiffre.")
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
    # Accept either the username or the email as the login identifier — users remember
    # their email, not the (often auto-derived) username. Lockout/reset below key on the
    # resolved id, so this stays safe.
    ident = username.strip()
    rows = db.fetch_query(
        "SELECT id, username, email, password_hash, artist_id, role, email_verified, "
        "       failed_login_attempts, locked_until, totp_enabled, totp_secret "
        "FROM saas_users WHERE (username = %s OR LOWER(email) = LOWER(%s)) "
        "AND active = TRUE LIMIT 1",
        (ident, ident)
    )
    if not rows:
        return None, _t("auth.invalid_credentials", "Identifiant ou mot de passe invalide.")

    uid, uname, email, pw_hash, artist_id, role, email_verified, fail_count, locked_until, totp_enabled, totp_secret = rows[0]

    # HIGH-01: check lockout before bcrypt (prevents timing oracle on locked accounts)
    if locked_until:
        now = datetime.now(timezone.utc)
        locked_until_aware = locked_until if locked_until.tzinfo else locked_until.replace(tzinfo=timezone.utc)
        if now < locked_until_aware:
            remaining = int((locked_until_aware - now).total_seconds() // 60) + 1
            return None, _t("auth.locked",
                            "Compte verrouillé après trop de tentatives échouées. "
                            "Réessayez dans {m} minute(s).").format(m=remaining)

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
        return None, _t("auth.invalid_credentials", "Nom d'utilisateur ou mot de passe invalide.")

    # Reset the failure counter only when the password was the LAST factor owed.
    # Resetting it here unconditionally is what made the TOTP challenge
    # brute-forceable (R26): the attacker knows the password, so every wrong code
    # could be followed by a fresh login that zeroed the counter again. With 2FA on,
    # the reset moves to _show_totp_challenge, after the code verifies.
    if not totp_enabled:
        db.execute_query(
            "UPDATE saas_users SET failed_login_attempts = 0, locked_until = NULL "
            "WHERE id = %s",
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
    from src.dashboard.utils.i18n import get_lang
    token = secrets.token_urlsafe(32)
    db.execute_query(
        "UPDATE saas_users SET verification_token = %s WHERE username = %s",
        (token, username)
    )
    if send_verification_email(email, username, token, lang=get_lang()):
        st.success(_t("auth.resend_ok",
                      "Email de vérification renvoyé à {email}.").format(email=email))
    else:
        st.error(_t("auth.resend_fail",
                    "Échec de l'envoi de l'email. Vérifiez la config SMTP dans config/config.yaml."))


def _hydrate_session(user: dict) -> None:
    st.session_state['authenticated'] = True
    # The row was just read by _authenticate_user; start the R24 re-read clock here
    # rather than firing a second identical query on the very next rerun.
    st.session_state['_last_reauth_at'] = time.time()
    st.session_state['username']      = user['username']
    st.session_state['name']          = user['email']
    st.session_state['artist_id']     = user['artist_id']  # None = admin
    st.session_state['role']          = user['role']
    st.session_state['user_id']       = user['id']
    # Restaurer la langue choisie lors d'une session précédente. `_hydrate_session`
    # est appelé APRÈS `session_state.clear()` (fixation de session MEDIUM-01), donc
    # c'est ici, et pas plus tôt, que le choix retrouve sa place.
    try:
        from src.dashboard.utils.lang_pref import load_preferred_lang
        preferred = load_preferred_lang(user['id'])
        if preferred:
            from src.dashboard.utils.i18n import set_lang
            set_lang(preferred)
    except Exception:  # noqa: BLE001 — une préférence illisible n'empêche pas d'entrer
        pass
    try:
        from src.dashboard.utils.usage_tracker import track
        track('login')
    except Exception:
        pass


# ─────────────────────────────────────────────
# TOTP 2FA challenge (Brick 28)
# ─────────────────────────────────────────────

def _record_second_factor_failure(db, username: str) -> None:
    """Count a wrong TOTP code against the account's lockout, like a wrong password.

    The lockout in `_authenticate_user` is the only counter that survives a new
    browser session. Leaving the second factor out of it meant an attacker holding
    the password had unlimited attempts at the code (R26) — the account never locked,
    because from the database's point of view nothing had failed.
    """
    if not username:
        return
    db.execute_query(
        "UPDATE saas_users SET failed_login_attempts = failed_login_attempts + 1, "
        "locked_until = CASE WHEN failed_login_attempts + 1 >= %s "
        "                    THEN NOW() + make_interval(mins => %s) ELSE locked_until END "
        "WHERE username = %s",
        (_MAX_LOGIN_ATTEMPTS, _LOCKOUT_MINUTES, username),
    )


def _show_totp_challenge(db) -> None:
    """Render the TOTP verification step after password auth succeeds."""
    pending = st.session_state.get('_totp_pending')
    if not pending:
        return

    st.title("🎵 streaMLytics")
    st.subheader(_t("auth.totp_title", "🔐 Authentification à deux facteurs"))
    st.info(_t("auth.totp_prompt",
               "Connecté en tant que **{u}**. Saisissez le code à 6 chiffres de votre "
               "application d'authentification.").format(u=pending['username']))

    with st.form("totp_challenge"):
        code = st.text_input(_t("auth.totp_code", "Code d'authentification"),
                             max_chars=6, placeholder="000000")
        col1, col2 = st.columns(2)
        submitted = col1.form_submit_button(_t("auth.totp_verify", "Vérifier"), type="primary")
        cancel    = col2.form_submit_button(_t("common.cancel", "Annuler"))

    if cancel:
        st.session_state.pop('_totp_pending', None)
        st.rerun()

    if submitted:
        # R26 — the budget for wrong codes lives OUTSIDE this session, keyed by client
        # IP. `_check_session_rate_limit()` counts in st.session_state, which a new
        # browser tab resets; and since the attacker knows the password, reforging a
        # `_totp_pending` in a fresh tab costs one request. That made a 6-digit code
        # with valid_window=1 reachable, not merely theoretically weak.
        from src.dashboard.utils.throttle import (
            throttle_check, throttle_record, throttle_reset,
        )
        retry_after = throttle_check("totp")
        if retry_after is not None:
            st.error(_t("auth.rate_limited",
                        "Trop de tentatives échouées. Réessayez dans {s} secondes."
                        ).format(s=retry_after))
            return
        try:
            import pyotp
            totp = pyotp.TOTP(pending['totp_secret'])
            if totp.verify(code.strip(), valid_window=1):
                user = dict(pending)
                st.session_state.pop('_totp_pending', None)
                _rate_reset()
                throttle_reset("totp")
                st.session_state.clear()
                _hydrate_session(user)
                # Both factors are now in: this is where the account-level lockout
                # counter is cleared, not after the password (see _authenticate_user).
                db.execute_query(
                    "UPDATE saas_users SET updated_at = NOW(), "
                    "failed_login_attempts = 0, locked_until = NULL WHERE username = %s",
                    (user['username'],)
                )
                st.rerun()
            else:
                throttle_record("totp")
                _rate_record_failure()
                # A wrong code is a failed login for the ACCOUNT too, so it walks
                # toward the same 5-attempt lockout a wrong password does. Without
                # this the only counter that moved was the one in this session.
                _record_second_factor_failure(db, pending.get('username', ''))
                st.error(_t("auth.totp_invalid", "Code d'authentification invalide. Réessayez."))
        except ImportError:
            st.error(_t("auth.totp_missing_dep",
                        "pyotp n'est pas installé. Exécutez : pip install pyotp"))


# ─────────────────────────────────────────────
# Bootstrap (first-run admin creation)
# ─────────────────────────────────────────────

def _show_bootstrap_form(db) -> None:
    st.title(_t("auth.bootstrap_title", "🎵 streaMLytics — Première configuration"))
    st.warning(
        _t("auth.bootstrap_warning",
           "Aucun utilisateur en base. Créez le premier compte **admin** pour commencer."),
        icon="⚠️",
    )
    with st.form("bootstrap_admin"):
        st.subheader(_t("auth.bootstrap_subheader", "Créer le compte admin"))
        username = st.text_input(_t("auth.username", "Nom d'utilisateur"))
        email    = st.text_input(_t("auth.email", "Email"))
        pw       = st.text_input(_t("auth.password", "Mot de passe"), type="password")
        pw2      = st.text_input(_t("auth.confirm_password", "Confirmer le mot de passe"),
                                 type="password")
        submitted = st.form_submit_button(_t("auth.bootstrap_submit", "Créer l'admin"),
                                          type="primary")

    if submitted:
        if not username or not email or not pw:
            st.error(_t("auth.all_fields_required", "Tous les champs sont obligatoires."))
            return
        if pw != pw2:
            st.error(_t("auth.pw_mismatch", "Les mots de passe ne correspondent pas."))
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
            st.success(_t("auth.bootstrap_ok",
                          "Compte admin '{u}' créé. Vous pouvez maintenant vous connecter.")
                       .format(u=username))
            st.rerun()
        except Exception as e:
            st.error(_t("auth.bootstrap_error",
                        "Erreur lors de la création de l'admin : {e}").format(e=e))


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
        now = time.time()
        if _session_idle_expired(st.session_state.get('_last_activity'), now):
            # C3: idle timeout — drop the whole session, fall through to the login form
            st.session_state.clear()
            st.session_state['_session_expired_notice'] = True
        elif not _session_still_authorised(now):
            # R24: the account was deactivated, deleted, or had its password changed
            # while this session was open. Fall through to the login form.
            st.session_state.clear()
            st.session_state['_session_revoked_notice'] = True
        else:
            st.session_state['_last_activity'] = now
            _maybe_bump_heartbeat()
            return True

    db = _get_db()
    if db is None:
        st.error(_t("auth.db_unreachable",
                    "❌ Base de données injoignable. Vérifiez que Docker est lancé : "
                    "`docker-compose up -d`"))
        return False

    try:
        if _user_table_empty(db):
            _show_bootstrap_form(db)
            return False

        # Brick 28: TOTP challenge takes priority over the login form
        if st.session_state.get('_totp_pending'):
            _show_totp_challenge(db)
            return False

        # Logo + pre-login language toggle on one row (toggle right-aligned, centered
        # vertically). The choice is persisted via ?lang= so it survives the post-auth
        # session reset and carries into the app + PDF export.
        from src.dashboard.utils import logo_html
        from src.dashboard.utils.i18n import language_selector
        _logo_col, _lang_col = st.columns([3, 1], vertical_alignment="center")
        with _logo_col:
            _logo = logo_html(variant="adaptive", max_width=320, center=True)
            if _logo:
                st.markdown(_logo, unsafe_allow_html=True)
            else:
                st.title("🎵 streaMLytics")
        with _lang_col:
            language_selector(sidebar=False)

        if st.session_state.pop('_session_expired_notice', None):
            st.info(_t("auth.session_expired",
                       "🔒 Session expirée après inactivité. Reconnectez-vous."))
        if st.session_state.pop('_session_revoked_notice', None):
            st.info(_t("auth.session_revoked",
                       "🔒 Votre session a pris fin : le compte a été désactivé ou "
                       "ses accès ont changé. Contactez un administrateur si c'est "
                       "inattendu."))

        with st.form("login"):
            st.subheader(_t("auth.signin_title", "Connexion"))
            # Login accepts the email OR the username (see _authenticate_user). Users
            # remember their email — surface it as the primary identifier.
            username  = st.text_input(_t("auth.username", "Email ou nom d'utilisateur"),
                                      key="login_username",
                                      placeholder=_t("auth.username_ph", "vous@exemple.com"),
                                      autocomplete="username")
            password  = st.text_input(_t("auth.password", "Mot de passe"), type="password",
                                      key="login_password",
                                      autocomplete="current-password")
            submitted = st.form_submit_button(_t("auth.signin", "Se connecter"), type="primary")

        st.markdown(_t("auth.register_link",
                       "[Pas encore de compte ? **Créez-en un**](?page=register)"))
        st.caption(_t("auth.pw_encrypted_notice",
                      "🔒 Votre mot de passe est chiffré (bcrypt) et n'est jamais stocké "
                      "en clair — conformément au RGPD."))

        if submitted:
            if not username or not password:
                st.error(_t("auth.enter_credentials",
                            "Veuillez saisir votre nom d'utilisateur et votre mot de passe."))
                return False

            # Brick 26: session-based rate limit check (a UX guard — a new tab
            # resets it, so it is not the security control).
            if not _check_session_rate_limit():
                return False
            # The security control: a per-IP budget that a new tab does not reset,
            # sitting IN FRONT of the per-account lockout. Password spraying — one
            # password across many accounts — never trips a per-account counter.
            from src.dashboard.utils.throttle import (
                throttle_check as _tc, throttle_record as _tr, throttle_reset as _trs,
            )
            _wait = _tc("login")
            if _wait is not None:
                st.error(_t("auth.rate_limited",
                            "Trop de tentatives échouées. Réessayez dans {s} secondes."
                            ).format(s=_wait))
                return False

            user, error = _authenticate_user(username, password, db)
            if user:
                _rate_reset()
                _trs("login")
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
            _tr("login")
            if error and error == "__unverified__":
                # HIGH-02: do not disclose the email address
                st.warning(_t(
                    "auth.verify_email_first",
                    "📧 Veuillez vérifier votre adresse email avant de vous connecter. "
                    "Consultez la boîte mail utilisée lors de l'inscription."
                ))
                if st.button(_t("auth.resend_btn", "Renvoyer l'email de vérification")):
                    # Look up email separately only after the user explicitly requests it
                    rows = db.fetch_query(
                        "SELECT email FROM saas_users WHERE username = %s AND active = TRUE LIMIT 1",
                        (username.strip(),)
                    )
                    if rows:
                        _resend_verification(username, rows[0][0], db)
            else:
                st.error(error or _t("auth.invalid_credentials",
                                     "Nom d'utilisateur ou mot de passe invalide."))
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

    role_label = (_t("auth.role_admin", "👑 Admin") if role == 'admin'
                  else _t("auth.role_artist", "🎤 Artiste"))
    st.sidebar.markdown(f"**{role_label}** — {name}")
    if artist_id is not None:
        st.sidebar.caption(f"artist_id = {artist_id}")
    else:
        st.sidebar.caption(_t("auth.global_access", "Accès global (tous les artistes)"))

    if st.sidebar.button(_t("auth.logout", "Se déconnecter")):
        # clear(), not a pop-list. `_SESSION_KEYS` named six keys and the session
        # holds more than six — `_totp_pending` carries the account's `totp_secret`
        # and survived a logout, as did the cached plan and the re-auth clock. A
        # hand-maintained list of things to forget grows a hole every time a key is
        # added; forgetting everything cannot.
        st.session_state.clear()
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


def tenant_scope() -> Optional[int]:
    """Whose data may this session read? None = every tenant. int = that one.

    THE point of this function is that it can never return None for a non-admin.

    `get_artist_id()` returns None for two entirely different situations — "this is
    an admin" and "this session has no tenant" — and its docstring has said since it
    was written that callers must tell them apart with `is_admin()`. Five call sites
    did not (R25, 2026-08-22): `home.py`, `spotify_s4a_combined.py`, `export_pdf.py`,
    `imusician.py`, and `artist_id_sql_filter()` right below, which is the one that
    matters because ~30 views reach the database through it. In all five, a missing
    id read as "no filter".

    That state — `role='artist'` with `artist_id IS NULL` — is not reachable through
    any wired path today; the schema allows it (`ON DELETE SET NULL`, migration
    007:9) and a function in `admin.py` would produce it. The honest summary is: not
    exploitable, one deletion away from being so, and free to close.

    Asking every caller to remember the two-line guard is what produced five that
    did not. This is the guard, once, with a name that says what it answers.
    """
    artist_id = get_artist_id()
    if artist_id is not None:
        return artist_id
    if is_admin():
        return None
    st.error(_t("ui.invalid_session", "Session invalide."))
    st.stop()


@st.cache_data(ttl=60, show_spinner=False)
def _cached_plan_row(artist_id: int):
    """Cache the raw plan row per artist (60s TTL) to stop the sidebar from opening a
    fresh DB connection on every rerun. The promo-expiry decision stays OUTSIDE the
    cache (evaluated fresh in get_artist_plan) so a just-expired promo isn't honored;
    only the DB read is memoized. A tier/subscription change self-heals within 60s."""
    from src.dashboard.utils import get_db_connection
    db = get_db_connection()
    if db is None:
        return None
    try:
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
    finally:
        db.close()
    return row[0] if row else None


def get_artist_plan() -> str:
    """Return the current artist's plan: 'free' | 'premium'.

    Reads artist_subscriptions from DB; falls back to saas_artists.tier. Any retired
    'basic' value is collapsed onto 'premium'. Returns 'premium' for admin sessions.
    """
    from src.database.stripe_schema import normalize_plan
    if is_admin():
        # Admin QA "Voir comme" selector: impersonate a tenant plan for the current
        # session so the free/premium nav + paywalls can be previewed. This previews
        # ACCESS only — data stays admin-wide (get_artist_id() is untouched).
        view_as = st.session_state.get('_view_as')
        if view_as in ('free', 'premium'):
            return view_as
        return 'premium'

    artist_id = get_artist_id()
    if artist_id is None:
        return 'premium'

    try:
        from datetime import datetime, timezone
        row = _cached_plan_row(artist_id)
        if not row:
            return 'free'

        promo_plan, promo_expires, subscription_plan, tier = row

        # Promo takes precedence if still active
        if promo_plan and (promo_expires is None or promo_expires > datetime.now(timezone.utc)):
            return normalize_plan(promo_plan)

        # Active Stripe subscription
        if subscription_plan:
            return normalize_plan(subscription_plan)

        # Legacy tier fallback
        if tier:
            return normalize_plan(tier)

    except Exception:
        pass
    return 'free'


def require_plan(min_plan: str) -> bool:
    """Show a paywall banner if the artist's plan is below min_plan.

    Returns True if access is allowed, False if blocked.
    """
    from src.database.stripe_schema import PLAN_CATALOG, PLAN_RANK
    current_plan = get_artist_plan()
    if PLAN_RANK.get(current_plan, 0) >= PLAN_RANK.get(min_plan, 0):
        return True

    plan_labels = {p: f"{c['label']} ({c['price_eur']}€/mo)" for p, c in PLAN_CATALOG.items()}
    st.warning(
        _t("auth.paywall",
           "🔒 Cette fonctionnalité nécessite le plan **{plan}**. "
           "Votre plan actuel : **{current}**.")
        .format(plan=plan_labels.get(min_plan, min_plan), current=current_plan),
        icon="⚠️",
    )
    if st.button(_t("auth.paywall_btn", "→ Voir les plans et upgrader"),
                 key=f"_upgrade_btn_{min_plan}"):
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

    # tenant_scope(), not get_artist_id(): the empty fragment below means "read
    # every tenant", and only an admin may be handed it (R25).
    artist_id = tenant_scope()
    if artist_id is None:
        return "", ()
    prefix = f"{table_alias}." if table_alias else ""
    return f"AND {prefix}artist_id = %s", (artist_id,)
