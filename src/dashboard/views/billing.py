"""Billing page — Brick 21.

Shows the current artist's subscription status, plan comparison,
and upgrade/manage links. Admin sees all artist subscriptions.
"""
import os
import streamlit as st
from src.dashboard.utils import get_db_connection
from src.dashboard.utils.i18n import t
from src.dashboard.auth import get_artist_id, is_admin, get_artist_plan
from src.database.stripe_schema import PLAN_CATALOG, PLAN_RANK, SERVICE_CONTACT_EMAIL


def _price_str(plan: str) -> str:
    p = PLAN_CATALOG[plan]['price_eur']
    if p == 0:
        return t("billing.price_free", "0 €/mois")
    return t("billing.price_monthly", "{p} €/mois").format(p=p)


# ── Plan display catalogue (3-column layout). Prices come from PLAN_CATALOG
# (single source of truth); curated bullets mirror PLAN_FEATURES (validated 2026-06-09:
# Export PDF in Free, Revenue forecast Premium-only, Basic 5€ / Premium 10€).
# Built per-render (not at import) so t() resolves the session language. ──
def _plan_cards() -> dict:
    return {
        'free': {
            'label': t("billing.plan_free_label", "🆓 Free"),
            'price': _price_str('free'),
            'max_artists': t("billing.one_artist", "1 artiste"),
            'features': [
                t("billing.feat_all_analytics",
                  "Toutes les analytics plateformes (Spotify, Apple Music, "
                  "YouTube, SoundCloud, Instagram, Meta Ads, Hypeddit)"),
                t("billing.feat_distributor",
                  "💰 Revenus distributeur (iMusician + DistroKid) + 🎼 royalties SACEM"),
                t("billing.feat_mapping",
                  "🔗 Mapping cross-plateforme — suggestions automatiques "
                  "(titres entre plateformes + campagnes Meta Ads)"),
                t("billing.feat_roi",
                  "💹 ROI Breakeven — revenus (distrib. + SACEM) vs dépenses Meta Ads"),
                t("billing.feat_csv", "📂 Import & export CSV / XLSX"),
                t("billing.feat_pdf", "📄 Export PDF du rapport (FR / EN)"),
                t("billing.feat_wrapped", "🎁 Data Wrapped annuel"),
                t("billing.feat_credentials", "🔑 Credentials API"),
            ],
        },
        'premium': {
            'label': t("billing.plan_premium_label", "💎 Premium"),
            'price': _price_str('premium'),
            'max_artists': t("billing.up_to_10", "Jusqu'à 10 artistes"),
            'features': [
                t("billing.feat_everything_free", "Tout ce que contient Free"),
                t("billing.feat_road_to_algo",
                  "🚀 Road to Algo — prédictions ML (machine learning) pour identifier les "
                  "leviers qui déclenchent les playlists algorithmiques Spotify : "
                  "Discover Weekly, Release Radar, Radio"),
                t("billing.feat_revenue_forecast", "📈 Prévisions de revenus (ML)"),
                t("billing.feat_creatives", "🎨 Créatives Meta Ads"),
                t("billing.feat_cpr", "📊 CPR Optimizer"),
                t("billing.feat_support", "Support prioritaire"),
            ],
        },
    }


_PLAN_ORDER = ['free', 'premium']


def show():
    st.title(t("billing.title", "💳 Facturation & Abonnement"))
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

        _render_service_cta()

    finally:
        db.close()


def _render_service_cta() -> None:
    """Done-for-you marketing-campaign optimization — manual service, call-first."""
    st.markdown("---")
    st.subheader(t("billing.service_header",
                   "🎯 Optimisation de vos campagnes marketing (service sur-mesure)"))
    st.markdown(
        t("billing.service_body",
          "Vous voulez déléguer l'optimisation de vos campagnes (Meta Ads & cie) ? "
          "Je peux m'en occuper directement. **Un appel préalable est requis** pour vérifier "
          "que ça colle à votre projet et définir le budget que vous souhaitez investir.\n\n"
          "📧 Contact : **{email}**").format(email=SERVICE_CONTACT_EMAIL)
    )
    st.link_button(
        t("billing.service_btn", "✉️ Me contacter pour l'optimisation"),
        f"mailto:{SERVICE_CONTACT_EMAIL}?subject=Optimisation%20campagnes%20marketing%20-%20streaMLytics",
    )


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
            st.info(t("billing.free_plan_info",
                      "Vous êtes sur le plan **Free**. Découvrez les offres ci-dessous."))
        else:
            st.success(
                t("billing.trial_active",
                  "🎁 Accès **{plan}** actif (essai de bienvenue). "
                  "Voir les offres ci-dessous pour la suite.").format(plan=plan.capitalize())
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
    col1.metric(t("billing.metric_plan", "Plan"), plan_name.capitalize())
    col2.metric(t("billing.metric_price", "Prix mensuel"), f"{float(price):.2f} €")
    col3.metric(t("billing.metric_status", "Statut"), f"{status_color} {status.replace('_', ' ').title()}")

    free_months_row = db.fetch_query(
        "SELECT referral_free_months FROM saas_artists WHERE id = %s", (artist_id,)
    )
    free_months = free_months_row[0][0] if free_months_row else 0
    if free_months > 0:
        st.success(t("billing.free_months",
                     "🎁 Vous avez **{n} mois gratuit(s)** grâce au parrainage — appliqués "
                     "avant votre prochain cycle de facturation.").format(n=free_months))

    discount_row = db.fetch_query(
        "SELECT first_month_discount_pct FROM saas_artists WHERE id = %s", (artist_id,)
    )
    discount_pct = discount_row[0][0] if discount_row else 0
    if discount_pct > 0:
        st.info(t("billing.discount",
                  "🏷️ Un **rabais de {pct}%** sera appliqué à votre premier mois payant "
                  "(récompense parrainage).").format(pct=discount_pct))

    if period_end:
        if cancel_at_end:
            st.warning(
                t("billing.cancel_warning",
                  "⚠️ Votre abonnement sera **résilié le {date}**. "
                  "Réactivez-le via le portail Stripe ci-dessous.").format(
                      date=period_end.strftime('%Y-%m-%d'))
            )
        else:
            st.caption(t("billing.next_renewal", "Prochain renouvellement : {date}").format(
                date=period_end.strftime('%Y-%m-%d')))

    if status == 'past_due':
        st.error(
            t("billing.payment_failed",
              "❌ Votre dernier paiement a échoué. Mettez à jour votre moyen de paiement "
              "pour rétablir l'accès."),
            icon="💳",
        )

    if customer_id:
        stripe_portal_url = os.getenv("STRIPE_PORTAL_URL", "")
        if stripe_portal_url:
            st.link_button(t("billing.manage_sub", "Gérer l'abonnement (portail Stripe)"), stripe_portal_url)
        else:
            st.caption(
                t("billing.portal_unset",
                  "Pour gérer votre abonnement, contactez le support ou définissez "
                  "`STRIPE_PORTAL_URL` dans votre environnement.")
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
        st.success(t("billing.current_plan_badge", "✅ Votre plan actuel"))
        return
    # Lower or equal rank than the current plan → already included
    if current_plan is not None and PLAN_RANK[target_plan] <= PLAN_RANK[current_plan]:
        st.caption(t("billing.included", "Inclus dans votre plan"))
        return
    if target_plan == 'free':
        st.caption(t("billing.free_no_action", "Plan gratuit — aucune action requise"))
        return

    checkout_url = os.getenv("STRIPE_CHECKOUT_URL", "")
    label = t("billing.upgrade_to", "Passer à {plan}").format(plan=target_plan.capitalize())
    if checkout_url:
        st.link_button(label, f"{checkout_url}?plan={target_plan}", type="primary")
    else:
        # No Stripe configured: enabled button that surfaces the manual path.
        if st.button(label, type="primary", key=f"upgrade_{target_plan}"):
            st.info(
                t("billing.payment_soon",
                  "💳 Le paiement en ligne arrive bientôt. En attendant, "
                  "contactez-nous pour activer ce plan dès maintenant.")
            )


def _render_plan_columns(current_plan: str | None) -> None:
    """3-column Free / Basic / Premium offer layout (replaces the table)."""
    st.subheader(t("billing.offers_header", "Nos offres"))
    plan_cards = _plan_cards()
    cols = st.columns(len(_PLAN_ORDER))
    for col, plan_key in zip(cols, _PLAN_ORDER):
        card = plan_cards[plan_key]
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
    st.subheader(t("billing.admin_header", "Tous les abonnements artistes"))

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
        st.info(t("billing.no_artists", "Aucun artiste trouvé."))
        return

    import pandas as pd
    df = pd.DataFrame(rows, columns=["Artist", "Tier", "Plan", "Status", "Period End", "Stripe Customer"])
    df["Period End"] = df["Period End"].apply(lambda x: x.strftime('%Y-%m-%d') if x else "—")
    df["Stripe Customer"] = df["Stripe Customer"].apply(lambda x: x[:8] + "…" if x else "—")
    df.columns = [
        t("common.artist", "Artiste"),
        t("billing.col_tier", "Tier"),
        t("billing.col_plan", "Plan"),
        t("billing.col_status", "Statut"),
        t("billing.col_period_end", "Fin de période"),
        t("billing.col_stripe", "Client Stripe"),
    ]
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
        st.subheader(t("billing.mrr_header", "Répartition du MRR"))
        col1, col2, col3 = st.columns(3)
        total_mrr = sum(float(r[2] or 0) for r in rev_rows)
        total_artists = sum(int(r[1]) for r in rev_rows)
        col1.metric(t("billing.total_mrr", "MRR total"), f"{total_mrr:.2f} €")
        col2.metric(t("billing.paying_artists", "Artistes payants"), total_artists)
        col3.metric("ARPU", f"{(total_mrr / total_artists):.2f} €" if total_artists else "—")

        import pandas as pd
        df_mrr = pd.DataFrame(rev_rows, columns=[
            t("billing.col_plan", "Plan"),
            t("billing.col_artists", "Artistes"),
            t("billing.col_mrr", "MRR (€)"),
        ])
        st.dataframe(df_mrr, width="stretch", hide_index=True)
