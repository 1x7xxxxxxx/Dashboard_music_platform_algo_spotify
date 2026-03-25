"""Billing page — Brick 21.

Shows the current artist's subscription status, plan comparison,
and upgrade/manage links. Admin sees all artist subscriptions.
"""
import streamlit as st
from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id, is_admin, get_artist_plan


def show():
    st.title("💳 Billing & Subscription")
    st.markdown("---")

    db = get_db_connection()
    artist_id = get_artist_id()
    admin = is_admin()

    try:
        # ── Current plan ─────────────────────────────────────────────────
        if not admin and artist_id:
            _show_current_plan(db, artist_id)
        elif admin:
            _show_admin_view(db)

        st.markdown("---")

        # ── Plan comparison table ─────────────────────────────────────────
        _show_plan_comparison(db)

    finally:
        db.close()


def _show_current_plan(db, artist_id: int):
    row = db.fetch_query(
        """
        SELECT sp.name, sp.price_monthly, asub.status,
               asub.current_period_end, asub.cancel_at_period_end,
               asub.stripe_customer_id, asub.stripe_subscription_id
        FROM artist_subscriptions asub
        JOIN subscription_plans sp ON sp.id = asub.plan_id
        WHERE asub.artist_id = %s
        LIMIT 1
        """,
        (artist_id,),
    )

    if not row:
        # No subscription row → free plan
        st.info("You are on the **Free** plan. Upgrade to unlock more features.")
        _show_upgrade_section()
        return

    plan_name, price, status, period_end, cancel_at_end, customer_id, sub_id = row[0]

    status_color = {
        'active': '🟢',
        'trialing': '🟡',
        'past_due': '🔴',
        'canceled': '⚫',
    }.get(status, '⚪')

    col1, col2, col3 = st.columns(3)
    col1.metric("Plan", plan_name.capitalize())
    col2.metric("Monthly price", f"{float(price):.2f} €")
    col3.metric("Status", f"{status_color} {status.replace('_', ' ').title()}")

    if period_end:
        if cancel_at_end:
            st.warning(
                f"⚠️ Your subscription is set to **cancel on {period_end.strftime('%Y-%m-%d')}**. "
                "Reactivate via the Stripe portal below."
            )
        else:
            st.caption(f"Next renewal: {period_end.strftime('%Y-%m-%d')}")

    if status == 'past_due':
        st.error(
            "❌ Your last payment failed. Update your payment method to restore access.",
            icon="💳",
        )

    if customer_id:
        stripe_portal_url = st.secrets.get("STRIPE_PORTAL_URL", "") if hasattr(st, 'secrets') else ""
        if stripe_portal_url:
            st.link_button("Manage subscription (Stripe portal)", stripe_portal_url)
        else:
            st.caption(
                "To manage your subscription, contact support or set `STRIPE_PORTAL_URL` in your environment."
            )

    if plan_name != 'premium':
        st.markdown("---")
        _show_upgrade_section(current_plan=plan_name)


def _show_upgrade_section(current_plan: str = 'free'):
    st.subheader("Upgrade your plan")

    checkout_url = st.secrets.get("STRIPE_CHECKOUT_URL", "") if hasattr(st, 'secrets') else ""

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Basic — 9.90 €/mo")
        st.markdown("""
- All data sources (Meta, Instagram, SoundCloud, Apple Music)
- Up to 3 artists
- CSV import & export
- Credentials management
        """)
        if current_plan == 'free':
            if checkout_url:
                st.link_button("Upgrade to Basic", f"{checkout_url}?plan=basic", type="primary")
            else:
                st.button("Upgrade to Basic", disabled=True, help="Set STRIPE_CHECKOUT_URL to enable")

    with col2:
        st.markdown("#### Premium — 29.90 €/mo")
        st.markdown("""
- Everything in Basic
- ML predictions + trigger algo
- Data Wrapped annual report
- PDF export
- Up to 10 artists
- Weekly email digest
        """)
        if current_plan in ('free', 'basic'):
            if checkout_url:
                st.link_button("Upgrade to Premium", f"{checkout_url}?plan=premium", type="primary")
            else:
                st.button("Upgrade to Premium", disabled=True, help="Set STRIPE_CHECKOUT_URL to enable")


def _show_admin_view(db):
    st.subheader("All artist subscriptions")

    rows = db.fetch_query(
        """
        SELECT sa.name, sa.tier, sp.name AS plan, asub.status,
               asub.current_period_end, asub.stripe_customer_id
        FROM saas_artists sa
        LEFT JOIN artist_subscriptions asub ON asub.artist_id = sa.id
        LEFT JOIN subscription_plans sp ON sp.id = asub.plan_id
        WHERE sa.active = TRUE
        ORDER BY sa.id
        """
    )

    if not rows:
        st.info("No artists found.")
        return

    import pandas as pd
    df = pd.DataFrame(rows, columns=["Artist", "Tier", "Plan", "Status", "Period End", "Stripe Customer"])
    df["Period End"] = df["Period End"].apply(lambda x: x.strftime('%Y-%m-%d') if x else "—")
    df["Stripe Customer"] = df["Stripe Customer"].apply(lambda x: x[:8] + "…" if x else "—")
    st.dataframe(df, width="stretch", hide_index=True)

    # Revenue summary
    rev_rows = db.fetch_query(
        """
        SELECT sp.name, COUNT(*) AS artists, SUM(sp.price_monthly) AS mrr
        FROM artist_subscriptions asub
        JOIN subscription_plans sp ON sp.id = asub.plan_id
        WHERE asub.status = 'active'
        GROUP BY sp.name, sp.price_monthly
        ORDER BY sp.price_monthly DESC
        """
    )

    if rev_rows:
        st.markdown("---")
        st.subheader("MRR breakdown")
        col1, col2, col3 = st.columns(3)
        total_mrr = sum(float(r[2] or 0) for r in rev_rows)
        total_artists = sum(int(r[1]) for r in rev_rows)
        col1.metric("Total MRR", f"{total_mrr:.2f} €")
        col2.metric("Paying artists", total_artists)
        col3.metric("ARPU", f"{(total_mrr / total_artists):.2f} €" if total_artists else "—")

        import pandas as pd
        df_mrr = pd.DataFrame(rev_rows, columns=["Plan", "Artists", "MRR (€)"])
        st.dataframe(df_mrr, width="stretch", hide_index=True)


def _show_plan_comparison(db):
    st.subheader("Plan comparison")

    rows = db.fetch_query(
        "SELECT name, price_monthly, max_artists, features FROM subscription_plans WHERE active ORDER BY price_monthly"
    )

    if not rows:
        return

    import json
    import pandas as pd

    table_data = []
    for name, price, max_artists, features_raw in rows:
        try:
            features = json.loads(features_raw) if isinstance(features_raw, str) else (features_raw or [])
        except Exception:
            features = []
        table_data.append({
            "Plan": name.capitalize(),
            "Price/mo": f"{float(price):.2f} €",
            "Max artists": max_artists,
            "Features": "All" if "*" in features else ", ".join(features),
        })

    st.dataframe(pd.DataFrame(table_data), width="stretch", hide_index=True)
