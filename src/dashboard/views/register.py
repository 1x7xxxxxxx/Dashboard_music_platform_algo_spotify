"""Registration view — New artist sign-up.

Type: Feature
Uses: get_db_connection, hash_password, send_verification_email
Depends on: saas_artists table, saas_users table
Persists in: PostgreSQL spotify_etl (saas_artists + saas_users, atomic CTE insert)

Accessible without login via /?page=register.
"""
import re
import secrets
import streamlit as st

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import hash_password
from src.utils.verification_email import send_verification_email


_SLUG_RE    = re.compile(r'^[a-z0-9_-]+$')
_USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{3,50}$')


def _validate(artist_name, slug, username, email, pw, pw2, terms: bool) -> list[str]:
    errors = []
    if not artist_name.strip():
        errors.append("Artist name is required.")
    if not _SLUG_RE.fullmatch(slug):
        errors.append("Slug: lowercase letters, digits, hyphens and underscores only.")
    if not _USERNAME_RE.fullmatch(username):
        errors.append("Username: 3–50 characters, letters/digits/underscores only.")
    if not email or '@' not in email:
        errors.append("A valid email address is required.")
    if len(pw) < 8:
        errors.append("Password must be at least 8 characters.")
    if pw != pw2:
        errors.append("Passwords do not match.")
    if not terms:
        errors.append("You must accept the Privacy Policy and Terms of Use to register.")
    return errors


def _username_taken(db, username: str) -> bool:
    return bool(db.fetch_query(
        "SELECT 1 FROM saas_users WHERE username = %s", (username,)
    ))


def _email_taken(db, email: str) -> bool:
    return bool(db.fetch_query(
        "SELECT 1 FROM saas_users WHERE email = %s", (email,)
    ))


def _slug_taken(db, slug: str) -> bool:
    return bool(db.fetch_query(
        "SELECT 1 FROM saas_artists WHERE slug = %s", (slug,)
    ))


def _create_artist_and_user(
    db, artist_name, slug, username, email, pw, token: str,
    marketing_consent: bool = False,
) -> int:
    """Atomic insert: saas_artists + saas_users via CTE.

    Returns the new saas_users.id.
    autocommit=True on the handler — CTE executes as a single statement,
    so either both rows are created or neither is.
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    rows = db.fetch_query(
        """
        WITH new_artist AS (
            INSERT INTO saas_artists (name, slug, tier, active)
            VALUES (%s, %s, 'free', TRUE)
            RETURNING id
        )
        INSERT INTO saas_users
            (username, email, password_hash, artist_id, role, active,
             email_verified, verification_token,
             terms_accepted, terms_accepted_at,
             marketing_consent, marketing_consent_at)
        SELECT %s, %s, %s, id, 'artist', TRUE, FALSE, %s,
               TRUE, %s,
               %s, %s
        FROM new_artist
        RETURNING id
        """,
        (artist_name.strip(), slug.strip(),
         username.strip(), email.strip(), hash_password(pw), token,
         now,
         marketing_consent, now if marketing_consent else None)
    )
    return rows[0][0]


def show():
    st.title("🎵 Create your account")
    st.caption("Join the Music Dashboard. Free plan — upgrade anytime.")

    with st.form("register"):
        col1, col2 = st.columns(2)

        artist_name = col1.text_input(
            "Artist name *",
            placeholder="e.g. 1x7xxxxxxx",
            help="Your public artist name.",
        )
        slug = col2.text_input(
            "Slug *",
            placeholder="e.g. 1x7xxxxxxx",
            help="Unique identifier — lowercase, no spaces. Auto-filled from artist name.",
        )

        # Auto-fill slug from artist name
        if artist_name and not slug:
            slug = re.sub(r'[^a-z0-9_-]', '-', artist_name.lower().strip())
            slug = re.sub(r'-+', '-', slug).strip('-')

        username = st.text_input(
            "Username *",
            placeholder="e.g. john_artist",
            help="Used to log in. 3–50 characters.",
        )
        email = st.text_input("Email *", placeholder="you@example.com")

        col3, col4 = st.columns(2)
        pw  = col3.text_input("Password *", type="password", help="Minimum 8 characters.")
        pw2 = col4.text_input("Confirm password *", type="password")

        st.markdown("---")
        terms = st.checkbox(
            "I accept the [Privacy Policy](?page=privacy) and Terms of Use *",
            value=False,
            help="Required to create an account.",
        )
        marketing = st.checkbox(
            "I agree to receive news, updates and marketing communications by email (optional)",
            value=False,
            help="You can withdraw this consent at any time.",
        )

        submitted = st.form_submit_button("Create account", type="primary")

    st.markdown("[Already have an account? **Sign in**](?page=login)")

    if not submitted:
        return

    errors = _validate(artist_name, slug, username, email, pw, pw2, terms)
    if errors:
        for e in errors:
            st.error(e)
        return

    db = get_db_connection()
    if db is None:
        st.error("❌ Database unreachable. Make sure Docker is running.")
        return

    try:
        if _slug_taken(db, slug):
            st.error(f"Slug '{slug}' is already taken. Choose a different one.")
            return
        if _username_taken(db, username):
            st.error(f"Username '{username}' is already taken.")
            return
        if _email_taken(db, email):
            st.error(f"Email '{email}' is already registered.")
            return

        token = secrets.token_urlsafe(32)
        _create_artist_and_user(
            db, artist_name, slug, username, email, pw, token,
            marketing_consent=marketing,
        )

        email_sent = send_verification_email(email, username, token)
        if email_sent:
            st.success(
                f"✅ Account created for **{artist_name}**! "
                f"A verification email has been sent to **{email}**. "
                "Click the link in the email to activate your account."
            )
        else:
            st.warning(
                f"✅ Account created for **{artist_name}**, but the verification email "
                "could not be sent (SMTP not configured). "
                "Ask an admin to manually verify your account."
            )

    except Exception as e:
        st.error(f"Registration failed: {e}")
    finally:
        db.close()
