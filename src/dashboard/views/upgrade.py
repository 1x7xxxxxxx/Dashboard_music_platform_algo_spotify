"""Plan comparison paywall page — shown when a locked feature is clicked.

Type: Feature
Uses: get_artist_plan, PLAN_FEATURES, PLAN_RANK
Depends on: billing view (Stripe portal CTA)
"""
import streamlit as st

from src.dashboard.auth import get_artist_plan
from src.database.stripe_schema import (
    PLAN_CATALOG, PLAN_FEATURES, PLAN_RANK, SERVICE_CONTACT_EMAIL,
)


def _price_label(plan: str) -> str:
    p = PLAN_CATALOG[plan]['price_eur']
    return "0€" if p == 0 else f"{p}€/mo"


# Human-readable labels for each page key
_PAGE_LABELS = {
    'home': 'Accueil',
    'spotify_s4a_combined': 'Spotify & S4A',
    'youtube': 'YouTube',
    'meta_ads_overview': 'Meta Ads - Vue d\'ensemble',
    'instagram': 'Instagram',
    'soundcloud': 'SoundCloud',
    'apple_music': 'Apple Music',
    'hypeddit': 'Hypeddit',
    'imusician': 'Distributeur (iMusician)',
    'upload_csv': 'Import CSV',
    'credentials': 'Credentials API',
    'export_csv': 'Export CSV',
    'data_wrapped': 'Data Wrapped',
    'trigger_algo': '🚀 Road to Algo (ML)',
    'export_pdf': 'Export PDF',
    'revenue_forecast': 'Prévisions revenus',
    'meta_x_spotify': 'META x Spotify',
    'meta_mapping': 'Meta Mapping',
    'account': 'Mon compte',
    'billing': 'Billing',
}

_PLAN_DISPLAY = {
    'free':    {'label': 'Free',    'price': _price_label('free'),    'color': '#6c757d'},
    'premium': {'label': 'Premium', 'price': _price_label('premium'), 'color': '#fd7e14'},
}


def _feature_list(plan: str) -> list[str]:
    """Return readable feature list for a given plan (premium = extras over Free)."""
    if plan == 'premium':
        return [
            '🚀 Road to Algo — prédictions ML',
            '📈 Prévisions de revenus (ML)',
            '🎨 Créatives Meta Ads',
            '📊 CPR Optimizer',
            'META x Spotify',
            'Support prioritaire',
        ]
    keys = PLAN_FEATURES.get(plan, set())
    return [_PAGE_LABELS.get(k, k) for k in sorted(keys)]


def show() -> None:
    current_plan = get_artist_plan()
    current_rank = PLAN_RANK.get(current_plan, 0)

    st.title("🔒 Passez à un plan supérieur")
    st.caption(
        f"Votre plan actuel : **{_PLAN_DISPLAY[current_plan]['label']}**. "
        "Débloquez plus de fonctionnalités en upgradeant."
    )
    st.markdown("---")

    col_free, col_premium = st.columns(2)

    # ── FREE ──────────────────────────────────────────────
    with col_free:
        is_current = current_plan == 'free'
        st.markdown(
            f"### {_PLAN_DISPLAY['free']['label']}"
            + (" ← *votre plan*" if is_current else "")
        )
        st.markdown(f"**{_PLAN_DISPLAY['free']['price']}**")
        st.markdown("---")
        for feat in _feature_list('free'):
            st.markdown(f"✅ {feat}")
        if is_current:
            st.success("Plan actuel")

    # ── PREMIUM ───────────────────────────────────────────
    with col_premium:
        is_current = current_plan == 'premium'
        can_upgrade = current_rank < PLAN_RANK['premium']
        st.markdown(
            f"### {_PLAN_DISPLAY['premium']['label']}"
            + (" ← *votre plan*" if is_current else "")
        )
        st.markdown(f"**{_PLAN_DISPLAY['premium']['price']}**")
        st.markdown("---")
        st.markdown("✅ **Tout le contenu Free, plus :**")
        for feat in _feature_list('premium'):
            st.markdown(f"✅ {feat}")
        st.markdown("---")
        if is_current:
            st.success("Plan actuel")
        elif can_upgrade:
            st.link_button("Passer à Premium →", "/?page=billing", type="primary")

    st.markdown("---")
    st.caption(
        "Les paiements sont gérés via Stripe. "
        "Annulation possible à tout moment depuis la page Billing."
    )
    st.markdown(
        "🎯 **Besoin qu'on optimise vos campagnes marketing pour vous ?** Service sur-mesure "
        f"(appel préalable pour valider le fit + le budget) — 📧 [{SERVICE_CONTACT_EMAIL}]"
        f"(mailto:{SERVICE_CONTACT_EMAIL}?subject=Optimisation%20campagnes%20-%20streaMLytics)"
    )
