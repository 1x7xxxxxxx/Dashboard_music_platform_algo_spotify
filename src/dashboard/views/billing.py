"""Billing page — Brick 21.

Shows the current artist's subscription status, plan comparison,
and upgrade/manage links. Admin sees all artist subscriptions.
"""
import os
import streamlit as st
from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id, is_admin, get_artist_plan


# ── Plan display catalogue (single source of truth for the 3-column layout) ──
# Prices align with migration 014 (Basic 5€, Premium 15€). Features are folded
# in here so the page no longer needs a separate comparison table.
_PLAN_CARDS = {
    'free': {
        'label': '🆓 Free',
        'price': '0 €/mois',
        'max_artists': '1 artiste',
        'features': [
            "Toutes les analytics plateformes (Spotify, Apple Music, "
            "YouTube, SoundCloud, Instagram, Meta Ads, Hypeddit)",
            "Revenus distributeur (iMusician)",
            "Import & export CSV",
            "Data Wrapped annuel",
            "Credentials API & mapping Meta × Spotify",
        ],
    },
    'basic': {
        'label': '⭐ Basic',
        'price': '5 €/mois',
        'max_artists': "Jusqu'à 3 artistes",
        'features': [
            "Tout ce que contient Free",
            "🚀 Road to Algo — prédictions ML",
            "📈 Prévisions de revenus (ML)",
            "📄 Export PDF",
        ],
    },
    'premium': {
        'label': '💎 Premium',
        'price': '15 €/mois',
        'max_artists': "Jusqu'à 10 artistes",
        'features': [
            "Tout ce que contient Basic",
            "🎨 Créatives Meta Ads",
            "📊 CPR Optimizer",
            "Support prioritaire",
        ],
    },
}
_PLAN_ORDER = ['free', 'basic', 'premium']
_PLAN_RANK = {'free': 0, 'basic': 1, 'premium': 2}


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

        # ── Offres (3 colonnes Free / Basic / Premium) ───────────────────
        # authoritative plan (includes the promo/trial precedence)
        current_plan = None if admin else get_artist_plan()
        _render_plan_columns(current_plan)

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
        # No subscription row → free plan (or active promo trial)
        plan = get_artist_plan()
        if plan == 'free':
            st.info("Vous êtes sur le plan **Free**. Découvrez les offres ci-dessous.")
        else:
            st.success(
                f"🎁 Accès **{plan.capitalize()}** actif (essai de bienvenue). "
                "Voir les offres ci-dessous pour la suite."
            )
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

    free_months_row = db.fetch_query(
        "SELECT referral_free_months FROM saas_artists WHERE id = %s", (artist_id,)
    )
    free_months = free_months_row[0][0] if free_months_row else 0
    if free_months > 0:
        st.success(f"🎁 You have **{free_months} free month(s)** from referrals — applied before your next billing cycle.")

    discount_row = db.fetch_query(
        "SELECT first_month_discount_pct FROM saas_artists WHERE id = %s", (artist_id,)
    )
    discount_pct = discount_row[0][0] if discount_row else 0
    if discount_pct > 0:
        st.info(f"🏷️ **{discount_pct}% discount** will be applied to your first paid month (referral reward).")

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
        stripe_portal_url = os.getenv("STRIPE_PORTAL_URL", "")
        if stripe_portal_url:
            st.link_button("Manage subscription (Stripe portal)", stripe_portal_url)
        else:
            st.caption(
                "To manage your subscription, contact support or set `STRIPE_PORTAL_URL` in your environment."
            )

    # Offres rendered by show() → _render_plan_columns (3-column layout).


def _upgrade_cta(target_plan: str, current_plan: str | None) -> None:
    """Render the call-to-action for one plan card.

    Greyed/disabled buttons are avoided: when Stripe checkout is not configured
    we still show an enabled button that explains how to upgrade, instead of a
    dead disabled control.
    """
    # Current plan → badge, no CTA
    if current_plan is not None and target_plan == current_plan:
        st.success("✅ Votre plan actuel")
        return
    # Lower or equal rank than the current plan → already included
    if current_plan is not None and _PLAN_RANK[target_plan] <= _PLAN_RANK[current_plan]:
        st.caption("Inclus dans votre plan")
        return
    if target_plan == 'free':
        st.caption("Plan gratuit — aucune action requise")
        return

    checkout_url = os.getenv("STRIPE_CHECKOUT_URL", "")
    label = f"Passer à {target_plan.capitalize()}"
    if checkout_url:
        st.link_button(label, f"{checkout_url}?plan={target_plan}", type="primary")
    else:
        # No Stripe configured: enabled button that surfaces the manual path.
        if st.button(label, type="primary", key=f"upgrade_{target_plan}"):
            st.info(
                "💳 Le paiement en ligne arrive bientôt. En attendant, "
                "contactez-nous pour activer ce plan dès maintenant."
            )


def _render_plan_columns(current_plan: str | None) -> None:
    """3-column Free / Basic / Premium offer layout (replaces the table)."""
    st.subheader("Nos offres")
    cols = st.columns(3)
    for col, plan_key in zip(cols, _PLAN_ORDER):
        card = _PLAN_CARDS[plan_key]
        with col:
            is_current = current_plan is not None and plan_key == current_plan
            header = f"### {card['label']}"
            if is_current:
                header += " ✅"
            st.markdown(header)
            st.markdown(f"**{card['price']}**  ·  {card['max_artists']}")
            st.markdown("\n".join(f"- {f}" for f in card['features']))
            st.markdown("")
            _upgrade_cta(plan_key, current_plan)


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
