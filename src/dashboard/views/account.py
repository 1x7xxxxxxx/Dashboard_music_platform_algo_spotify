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
from src.dashboard.auth import verify_password, hash_password


def _get_user_row(db, username: str) -> dict | None:
    rows = db.fetch_query(
        """
        SELECT u.id, u.username, u.email, u.password_hash, u.role,
               u.created_at, u.email_verified,
               u.terms_accepted, u.terms_accepted_at,
               u.marketing_consent, u.marketing_consent_at,
               a.name  AS artist_name,
               a.slug  AS artist_slug,
               a.tier  AS artist_tier
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
    if len(new_pw) < 8:
        st.error("New password must be at least 8 characters.")
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

    import pandas as pd

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

        tab_profile, tab_password, tab_consent, tab_data = st.tabs([
            "👤 Profile", "🔒 Password", "📧 Communications", "📦 My data"
        ])

        with tab_profile:
            _section_profile(user)

        with tab_password:
            _section_change_password(db, user)

        with tab_consent:
            _section_consent(db, user)

        with tab_data:
            _section_data_export(user)
            st.markdown("---")
            _section_delete_account()

    finally:
        db.close()
