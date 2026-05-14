"""Referral admin KPI page — admin-only.

Type: Feature
Uses: get_db_connection, is_admin
Depends on: referral_events, referral_codes, saas_artists, artist_subscriptions tables
Persists in: read-only view

Shows referral program metrics: total referrals, free months granted,
conversion rate, top referrers, and full event log.
"""
import streamlit as st
import pandas as pd

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import is_admin


def _guard():
    if not is_admin():
        st.error("⛔ Admin access only.")
        st.stop()


def show():
    _guard()
    st.title("📊 Referral Program — KPIs")
    st.markdown("---")

    db = get_db_connection()
    if db is None:
        st.error("❌ Database unreachable.")
        return

    try:
        # ── Global KPIs ────────────────────────────────────────────────────
        total_row = db.fetch_query("SELECT COUNT(*) FROM referral_events")
        total_referrals = total_row[0][0] if total_row else 0

        free_months_row = db.fetch_query(
            "SELECT COALESCE(SUM(referral_free_months), 0) FROM saas_artists"
        )
        total_free_months = free_months_row[0][0] if free_months_row else 0

        converted_row = db.fetch_query(
            """
            SELECT COUNT(DISTINCT re.referred_artist_id)
            FROM referral_events re
            JOIN artist_subscriptions asub ON asub.artist_id = re.referred_artist_id
            WHERE asub.status IN ('active', 'trialing')
            """
        )
        converted = converted_row[0][0] if converted_row else 0
        conversion_rate = f"{(converted / total_referrals * 100):.1f}%" if total_referrals else "—"

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total referrals", total_referrals)
        col2.metric("Converted to paid", converted)
        col3.metric("Conversion rate", conversion_rate)
        col4.metric("Free months granted", int(total_free_months))

        st.markdown("---")

        # ── Top referrers ──────────────────────────────────────────────────
        st.subheader("Top referrers")

        top_rows = db.fetch_query(
            """
            SELECT sa.name,
                   COUNT(re.id)               AS referrals_made,
                   sa.referral_free_months    AS free_months_earned,
                   rc.uses_count              AS code_uses,
                   rc.code
            FROM referral_events re
            JOIN saas_artists sa ON sa.id = re.referrer_artist_id
            LEFT JOIN referral_codes rc ON rc.artist_id = sa.id
            GROUP BY sa.id, sa.name, sa.referral_free_months, rc.uses_count, rc.code
            ORDER BY referrals_made DESC
            LIMIT 20
            """
        )

        if top_rows:
            df_top = pd.DataFrame(
                top_rows,
                columns=["Artist", "Referrals made", "Free months earned", "Code uses", "Code"],
            )
            st.dataframe(df_top, hide_index=True, width="stretch")
        else:
            st.info("No referrals recorded yet.")

        st.markdown("---")

        # ── Full event log ─────────────────────────────────────────────────
        st.subheader("All referral events")

        log_rows = db.fetch_query(
            """
            SELECT
                referrer.name                                       AS referrer,
                referred.name                                       AS referred,
                re.code_used,
                re.created_at::date                                 AS date,
                COALESCE(sp.name, 'free')                           AS referred_plan
            FROM referral_events re
            JOIN saas_artists referrer  ON referrer.id  = re.referrer_artist_id
            JOIN saas_artists referred  ON referred.id  = re.referred_artist_id
            LEFT JOIN artist_subscriptions asub ON asub.artist_id = re.referred_artist_id
            LEFT JOIN subscription_plans sp     ON sp.id          = asub.plan_id
            ORDER BY re.created_at DESC
            """
        )

        if log_rows:
            df_log = pd.DataFrame(
                log_rows,
                columns=["Referrer", "Referred", "Code used", "Date", "Referred's plan"],
            )
            df_log["Date"] = df_log["Date"].astype(str)
            st.dataframe(df_log, hide_index=True, width="stretch")
        else:
            st.info("No referral events yet.")

    finally:
        db.close()
