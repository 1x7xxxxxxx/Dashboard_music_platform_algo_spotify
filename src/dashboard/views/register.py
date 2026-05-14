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

from src.dashboard.utils import project_db
from src.dashboard.auth import hash_password, _validate_password_strength
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
    if not email or not re.fullmatch(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        errors.append("A valid email address is required.")
    pw_error = _validate_password_strength(pw)
    if pw_error:
        errors.append(pw_error)
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


def _validate_referral_code(db, code: str) -> int | None:
    """Return referrer artist_id for a valid code, or None if not found."""
    if not code:
        return None
    row = db.fetch_query(
        "SELECT artist_id FROM referral_codes WHERE code = %s",
        (code.upper(),),
    )
    return row[0][0] if row else None


def _validate_promo_code(db, code: str) -> dict | None:
    """Return promo code metadata if valid and redeemable, else None.

    Checks: active, not expired, uses_count < max_uses (0 = unlimited).
    MEDIUM-05: validation is read-only; the atomic increment happens in
    _apply_promo via a conditional UPDATE that re-checks the limit,
    preventing TOCTOU race conditions on single-use codes.
    """
    if not code:
        return None
    from datetime import datetime, timezone
    row = db.fetch_query(
        """
        SELECT id, plan_target, duration_days, max_uses, uses_count, expires_at
        FROM promo_codes
        WHERE code = %s AND active = TRUE
        """,
        (code.upper(),),
    )
    if not row:
        return None
    promo_id, plan_target, duration_days, max_uses, uses_count, expires_at = row[0]
    if expires_at and expires_at < datetime.now(timezone.utc):
        return None
    if max_uses > 0 and uses_count >= max_uses:
        return None
    return {
        'id': promo_id,
        'plan_target': plan_target,
        'duration_days': duration_days,
        'max_uses': max_uses,
    }


def _apply_promo(db, promo: dict, artist_id: int, code: str) -> None:
    """Set promo plan on artist and record the event.

    MEDIUM-05: uses a conditional UPDATE with a row-level guard to atomically
    increment uses_count only if the limit has not yet been reached.
    Concurrent registrations with the same single-use code will fail the
    UPDATE check and return 0 rows — the second caller is rejected safely.
    """
    from datetime import datetime, timezone, timedelta
    expires_at = datetime.now(timezone.utc) + timedelta(days=promo['duration_days'])

    # Atomic increment: only succeeds if max_uses not yet reached
    max_uses = promo.get('max_uses', 0)
    if max_uses > 0:
        incremented = db.fetch_query(
            """
            UPDATE promo_codes
            SET    uses_count = uses_count + 1
            WHERE  id = %s AND (max_uses = 0 OR uses_count < max_uses)
            RETURNING id
            """,
            (promo['id'],),
        )
        if not incremented:
            raise ValueError("Promo code already exhausted (race condition prevented).")
    else:
        db.execute_query(
            "UPDATE promo_codes SET uses_count = uses_count + 1 WHERE id = %s",
            (promo['id'],),
        )

    db.fetch_query(
        """
        UPDATE saas_artists
        SET promo_code_used = %s, promo_plan = %s, promo_plan_expires_at = %s
        WHERE id = %s
        """,
        (code, promo['plan_target'], expires_at, artist_id),
    )
    db.fetch_query(
        "INSERT INTO promo_events (promo_code_id, artist_id) VALUES (%s, %s)",
        (promo['id'], artist_id),
    )
    # Note: uses_count increment is already handled atomically above.


def _apply_referral(db, referrer_artist_id: int, referred_artist_id: int, code: str) -> None:
    """Credit referrer +1 free month and record the event."""
    db.fetch_query(
        "INSERT INTO referral_events (referrer_artist_id, referred_artist_id, code_used) VALUES (%s, %s, %s)",
        (referrer_artist_id, referred_artist_id, code),
    )
    db.fetch_query(
        "UPDATE saas_artists SET referral_free_months = referral_free_months + 1 WHERE id = %s",
        (referrer_artist_id,),
    )
    db.fetch_query(
        "UPDATE referral_codes SET uses_count = uses_count + 1 WHERE code = %s",
        (code,),
    )


def _create_artist_and_user(
    db, artist_name, slug, username, email, pw, token: str,
    marketing_consent: bool = False,
    referred_by_code: str = '',
    first_month_discount_pct: int = 0,
) -> tuple[int, int]:
    """Atomic insert: saas_artists + saas_users via CTE.

    Returns (saas_users.id, saas_artists.id).
    autocommit=True on the handler — CTE executes as a single statement,
    so either both rows are created or neither is.
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    rows = db.fetch_query(
        """
        WITH new_artist AS (
            INSERT INTO saas_artists
                (name, slug, tier, active, referred_by_code, first_month_discount_pct)
            VALUES (%s, %s, 'free', TRUE, %s, %s)
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
        RETURNING id, (SELECT id FROM new_artist)
        """,
        (artist_name.strip(), slug.strip(),
         referred_by_code or None, first_month_discount_pct,
         username.strip(), email.strip(), hash_password(pw), token,
         now,
         marketing_consent, now if marketing_consent else None)
    )
    user_id, artist_id = rows[0]
    return user_id, artist_id


def show():
    st.title("🎵 Create your account")
    st.caption("Join the Music Dashboard. Free plan — upgrade anytime.")

    # Brick 32 — Live Activity (public trust signal). Count only, no PII.
    # Cached 10 min server-side to absorb anonymous traffic bursts.
    from src.dashboard.utils.live_pulse import get_registered_count_public
    _registered = get_registered_count_public()
    if _registered > 0:
        st.metric("Live Activity", f"{_registered:,} artistes utilisent streaMLytics")
        st.markdown("---")

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

        referral_code = st.text_input(
            "Promo or referral code (optional)",
            placeholder="e.g. A3F8C1",
            help="Promo code (free access) or referral code from a friend (20% off first month).",
        ).strip().upper()

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

    with project_db() as db:
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

            # Resolve code type: promo takes priority over referral
            promo = None
            referrer_artist_id = None
            discount_pct = 0
            if referral_code:
                promo = _validate_promo_code(db, referral_code)
                if promo is None:
                    referrer_artist_id = _validate_referral_code(db, referral_code)
                    if referrer_artist_id is None:
                        st.error(f"Code '{referral_code}' is not valid or has expired.")
                        return
                    discount_pct = 20

            token = secrets.token_urlsafe(32)
            _user_id, new_artist_id = _create_artist_and_user(
                db, artist_name, slug, username, email, pw, token,
                marketing_consent=marketing,
                referred_by_code=referral_code if referrer_artist_id else '',
                first_month_discount_pct=discount_pct,
            )

            if promo is not None:
                _apply_promo(db, promo, new_artist_id, referral_code)
            elif referrer_artist_id is not None:
                _apply_referral(db, referrer_artist_id, new_artist_id, referral_code)

            if promo:
                discount_msg = f" Your **{promo['plan_target'].capitalize()} plan** is active for **{promo['duration_days']} days**."
            elif discount_pct:
                discount_msg = " Your **20% discount** will be applied to your first paid month."
            else:
                discount_msg = ""
            email_sent = send_verification_email(email, username, token)
            if email_sent:
                st.success(
                    f"✅ Account created for **{artist_name}**!{discount_msg} "
                    f"A verification email has been sent to **{email}**. "
                    "Click the link in the email to activate your account."
                )
            else:
                st.warning(
                    f"✅ Account created for **{artist_name}**,{discount_msg} but the verification email "
                    "could not be sent (SMTP not configured). "
                    "Ask an admin to manually verify your account."
                )
            st.link_button("→ Configurer votre dashboard (2 min)", "/?page=onboarding")

        except Exception as e:
            st.error(f"Registration failed: {e}")
