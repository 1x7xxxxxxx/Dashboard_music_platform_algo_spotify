"""Account self-service page — password change, consent management, data export.

Type: Feature
Uses: get_db_connection, verify_password, hash_password
Depends on: saas_users, saas_artists
RGPD: covers Art. 15 (access), Art. 16 (rectification), Art. 17 (partial — deletion via admin),
      Art. 21 (opposition marketing).
"""
import json
from datetime import datetime, timezone

import streamlit as st

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import verify_password, hash_password, _validate_password_strength


def _get_user_row(db, username: str) -> dict | None:
    rows = db.fetch_query(
        """
        SELECT u.id, u.username, u.email, u.password_hash, u.role,
               u.created_at, u.email_verified,
               u.terms_accepted, u.terms_accepted_at,
               u.marketing_consent, u.marketing_consent_at,
               a.name  AS artist_name,
               a.slug  AS artist_slug,
               a.tier  AS artist_tier,
               u.totp_enabled
        FROM saas_users u
        LEFT JOIN saas_artists a ON u.artist_id = a.id
        WHERE u.username = %s LIMIT 1
        """,
        (username,),
    )
    if not rows:
        return None
    cols = [
        "id", "username", "email", "password_hash", "role",
        "created_at", "email_verified",
        "terms_accepted", "terms_accepted_at",
        "marketing_consent", "marketing_consent_at",
        "artist_name", "artist_slug", "artist_tier",
        "totp_enabled",
    ]
    return dict(zip(cols, rows[0]))


# ─────────────────────────────────────────────
# Sections
# ─────────────────────────────────────────────

def _section_profile(user: dict) -> None:
    st.subheader("👤 My account")
    c1, c2, c3 = st.columns(3)
    c1.metric("Username", user["username"])
    c2.metric("Role", user["role"])
    c3.metric("Email verified", "✅ Yes" if user["email_verified"] else "⏳ Pending")

    st.caption(f"Email : **{user['email']}**")
    if user.get("artist_name"):
        st.caption(
            f"Artist : **{user['artist_name']}** — slug `{user['artist_slug']}` — tier `{user['artist_tier']}`"
        )
    joined = user.get("created_at")
    if joined:
        import pandas as pd
        st.caption(f"Member since : {pd.to_datetime(joined).strftime('%d %B %Y')}")


def _section_change_password(db, user: dict) -> None:
    st.subheader("🔒 Change password")
    with st.form("change_password"):
        current = st.text_input("Current password", type="password")
        new_pw  = st.text_input("New password", type="password", help="Minimum 8 characters.")
        new_pw2 = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button("Update password", type="primary")

    if not submitted:
        return

    if not current or not new_pw or not new_pw2:
        st.error("All three fields are required.")
        return
    if not verify_password(current, user["password_hash"]):
        st.error("Current password is incorrect.")
        return
    pw_error = _validate_password_strength(new_pw)
    if pw_error:
        st.error(pw_error)
        return
    if new_pw != new_pw2:
        st.error("Passwords do not match.")
        return
    if verify_password(new_pw, user["password_hash"]):
        st.warning("New password is identical to the current one.")
        return

    db.execute_query(
        "UPDATE saas_users SET password_hash = %s WHERE id = %s",
        (hash_password(new_pw), user["id"]),
    )
    st.success("✅ Password updated successfully.")


def _section_consent(db, user: dict) -> None:
    st.subheader("📧 Communication preferences")

    current_consent = bool(user.get("marketing_consent"))
    st.write(
        "You are currently **opted in**" if current_consent
        else "You are currently **opted out**"
        " of marketing communications (newsletters, platform news)."
    )
    if user.get("marketing_consent_at"):
        import pandas as pd
        st.caption(
            f"Last updated : {pd.to_datetime(user['marketing_consent_at']).strftime('%d/%m/%Y %H:%M')}"
        )

    new_consent = st.toggle(
        "Receive marketing communications by email",
        value=current_consent,
        key="marketing_toggle",
    )

    if new_consent != current_consent:
        now = datetime.now(timezone.utc)
        db.execute_query(
            "UPDATE saas_users SET marketing_consent = %s, marketing_consent_at = %s WHERE id = %s",
            (new_consent, now, user["id"]),
        )
        if new_consent:
            st.success("✅ You have opted in to marketing communications.")
        else:
            st.success("✅ You have opted out. You will no longer receive marketing emails.")
        st.rerun()


def _section_data_export(user: dict) -> None:
    st.subheader("📦 Export my data (RGPD Art. 15)")
    st.caption(
        "Download a copy of all personal data associated with your account. "
        "Operational data (streams, analytics) is not included — it belongs to the platform."
    )


    export = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": {
            "username":            user.get("username"),
            "email":               user.get("email"),
            "role":                user.get("role"),
            "email_verified":      user.get("email_verified"),
            "created_at":          str(user.get("created_at", "")),
            "terms_accepted":      user.get("terms_accepted"),
            "terms_accepted_at":   str(user.get("terms_accepted_at", "")),
            "marketing_consent":   user.get("marketing_consent"),
            "marketing_consent_at": str(user.get("marketing_consent_at", "")),
        },
        "artist": {
            "name": user.get("artist_name"),
            "slug": user.get("artist_slug"),
            "tier": user.get("artist_tier"),
        },
        "note": (
            "Credentials (API tokens) are stored encrypted and are not included in this export "
            "for security reasons. Contact the admin to obtain them separately."
        ),
    }

    st.download_button(
        label="⬇️ Download my data (JSON)",
        data=json.dumps(export, indent=2, ensure_ascii=False),
        file_name=f"my_data_{user['username']}.json",
        mime="application/json",
    )


def _section_totp(db, user: dict) -> None:
    """Brick 28 — TOTP 2FA enrollment and revocation."""
    st.subheader("🔐 Two-factor authentication (2FA)")

    totp_enabled = bool(user.get("totp_enabled"))

    if totp_enabled:
        st.success("✅ Two-factor authentication is **enabled** on your account.")
        st.caption("Your authenticator app is required at each sign-in.")
        st.markdown("---")
        st.write("**Disable 2FA**")
        with st.form("disable_totp"):
            pw = st.text_input("Confirm your password to disable 2FA", type="password")
            submitted = st.form_submit_button("Disable 2FA", type="secondary")
        if submitted:
            if not verify_password(pw, user["password_hash"]):
                st.error("Incorrect password.")
                return
            db.execute_query(
                "UPDATE saas_users SET totp_enabled = FALSE, totp_secret = NULL WHERE id = %s",
                (user["id"],),
            )
            st.success("✅ 2FA disabled. You can re-enable it at any time.")
            st.rerun()
        return

    # ── Enrollment flow ──────────────────────────────────────────────
    st.info("Protect your account with a time-based one-time password (TOTP). "
            "Compatible with Google Authenticator, Authy, and similar apps.")

    # Generate or reuse pending secret stored in session
    try:
        import pyotp
        import qrcode
        import io
    except ImportError:
        st.error("Required packages not installed: `pip install pyotp qrcode[pil]`")
        return

    if 'totp_enroll_secret' not in st.session_state:
        st.session_state['totp_enroll_secret'] = pyotp.random_base32()

    secret = st.session_state['totp_enroll_secret']
    issuer = "MusicDashboard"
    account = user["email"]
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=account, issuer_name=issuer)

    # Render QR code as PNG bytes
    qr_img = qrcode.make(uri)
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    buf.seek(0)

    col_qr, col_info = st.columns([1, 2])
    with col_qr:
        st.image(buf.getvalue(), caption="Scan with your authenticator app", width=200)
    with col_info:
        st.write("**Manual entry key:**")
        st.code(secret, language=None)
        st.caption("Enter this key manually in your app if you cannot scan the QR code.")

    st.markdown("---")
    st.write("**Verify and activate**")
    with st.form("enable_totp"):
        code = st.text_input("Enter the 6-digit code from your app", max_chars=6, placeholder="000000")
        submitted = st.form_submit_button("Activate 2FA", type="primary")

    if submitted:
        totp = pyotp.TOTP(secret)
        if totp.verify(code.strip(), valid_window=1):
            db.execute_query(
                "UPDATE saas_users SET totp_secret = %s, totp_enabled = TRUE WHERE id = %s",
                (secret, user["id"]),
            )
            st.session_state.pop('totp_enroll_secret', None)
            st.success("✅ Two-factor authentication is now active on your account.")
            st.rerun()
        else:
            st.error("Invalid code. Make sure your device clock is correct and try again.")


def _section_delete_account() -> None:
    st.subheader("🗑️ Delete my account (RGPD Art. 17)")
    st.warning(
        "Account deletion is handled by the administrator. "
        "Send a request to **1x7xxxxxxx@gmail.com** with the subject "
        "**'Delete my account — [your username]'**. "
        "Your data will be deleted within 30 days."
    )


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

def show() -> None:
    st.title("👤 My Account")
    st.markdown("---")

    username = st.session_state.get("username")
    if not username:
        st.error("Session expired. Please log in again.")
        return

    db = get_db_connection()
    if db is None:
        st.error("Database unreachable.")
        return

    try:
        user = _get_user_row(db, username)
        if user is None:
            st.error("User not found.")
            return

        tab_profile, tab_password, tab_2fa, tab_consent, tab_data = st.tabs([
            "👤 Profile", "🔒 Password", "🔐 2FA", "📧 Communications", "📦 My data"
        ])

        with tab_profile:
            _section_profile(user)

        with tab_password:
            _section_change_password(db, user)

        with tab_2fa:
            _section_totp(db, user)

        with tab_consent:
            _section_consent(db, user)

        with tab_data:
            _section_data_export(user)
            st.markdown("---")
            _section_delete_account()

    finally:
        db.close()
