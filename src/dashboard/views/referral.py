"""Referral page — artist-facing referral program.

Type: Feature
Uses: get_db_connection, get_artist_id
Depends on: referral_codes table, referral_events table, saas_artists table
Persists in: PostgreSQL spotify_etl (referral_codes, referral_events, saas_artists)

Accessible to all plans (free, basic, premium).
Each artist gets one unique code. Referrer earns +1 free month per successful referral.
"""
import secrets
import streamlit as st

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id


def _get_or_create_code(db, artist_id: int) -> str:
    """Return existing referral code for artist, or generate and insert a new one."""
    row = db.fetch_query(
        "SELECT code FROM referral_codes WHERE artist_id = %s",
        (artist_id,),
    )
    if row:
        return row[0][0]
    code = secrets.token_hex(3).upper()  # e.g. "A3F8C1"
    db.execute_query(
        "INSERT INTO referral_codes (artist_id, code) VALUES (%s, %s)",
        (artist_id, code),
    )
    return code


def show():
    st.title("🎁 Referral Program")
    st.caption("Share your code — earn 1 free month for each artist who subscribes with it.")

    artist_id = get_artist_id()
    if artist_id is None:
        st.info("Referral program is not available for admin accounts.")
        return

    db = get_db_connection()
    if db is None:
        st.error("❌ Database unreachable.")
        return

    try:
        code = _get_or_create_code(db, artist_id)

        # ── Your code ─────────────────────────────────────────────────────
        st.subheader("Your referral code")
        st.code(code, language=None)
        st.caption(
            "Code **unique** et permanent attribué à votre compte. Partagez-le : "
            "les artistes qui l'utilisent à l'inscription obtiennent **20% sur leur "
            "premier mois**. (Rappel : chaque nouvel inscrit reçoit aussi **30 jours "
            "d'accès Premium offerts** automatiquement.)"
        )

        st.markdown("---")

        # ── Referral stats ─────────────────────────────────────────────────
        stats = db.fetch_query(
            "SELECT referral_free_months FROM saas_artists WHERE id = %s",
            (artist_id,),
        )
        free_months = stats[0][0] if stats else 0

        uses_row = db.fetch_query(
            "SELECT uses_count FROM referral_codes WHERE artist_id = %s",
            (artist_id,),
        )
        total_referrals = uses_row[0][0] if uses_row else 0

        col1, col2 = st.columns(2)
        col1.metric("Artists referred", total_referrals)
        col2.metric("Free months earned", free_months)

        if free_months > 0:
            st.success(
                f"🎉 You have **{free_months} free month(s)** credited to your account. "
                "These will be applied before your next billing cycle."
            )

        st.markdown("---")

        # ── Referred artists list ──────────────────────────────────────────
        st.subheader("Artists you referred")

        rows = db.fetch_query(
            """
            SELECT sa.name, re.created_at::date AS joined_on
            FROM referral_events re
            JOIN saas_artists sa ON sa.id = re.referred_artist_id
            WHERE re.referrer_artist_id = %s
            ORDER BY re.created_at DESC
            """,
            (artist_id,),
        )

        if not rows:
            st.info("No referrals yet. Share your code to start earning free months!")
        else:
            import pandas as pd
            df = pd.DataFrame(rows, columns=["Artist", "Joined on"])
            df["Joined on"] = df["Joined on"].astype(str)
            st.dataframe(df, hide_index=True, width="stretch")

        st.markdown("---")

        # ── How it works ───────────────────────────────────────────────────
        with st.expander("How does it work?"):
            st.markdown("""
**For you (referrer):**
- Share your code with any artist.
- When they register and subscribe to a paid plan using your code, you automatically earn **+1 free month** on your current plan.
- Free months accumulate — no cap.

**For them (referred):**
- Enter the referral code during registration.
- Get **20% off their first paid month**.

**Limits:**
- Each code can only be used once per referred artist.
- Free months apply to your next billing cycle.
            """)

    finally:
        db.close()
