"""Plan comparison paywall page — shown when a locked feature is clicked.

Type: Feature
Uses: get_artist_plan, PLAN_FEATURES, PLAN_RANK
Depends on: billing view (Stripe portal CTA)
"""
import streamlit as st

from src.dashboard.auth import get_artist_plan
from src.database.stripe_schema import PLAN_FEATURES, PLAN_RANK


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
    'free':    {'label': 'Free',    'price': '0€',       'color': '#6c757d'},
    'basic':   {'label': 'Basic',   'price': '9.90€/mo', 'color': '#0d6efd'},
    'premium': {'label': 'Premium', 'price': '29.90€/mo','color': '#fd7e14'},
}


def _feature_list(plan: str) -> list[str]:
    """Return readable feature list for a given plan."""
    if plan == 'premium':
        return [
            'Tout le contenu Basic',
            '🚀 Road to Algo (ML scoring)',
            'Export PDF',
            'Prévisions revenus',
            'META x Spotify',
            'Meta Mapping',
            'Monitoring ETL (admin)',
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

    col_free, col_basic, col_premium = st.columns(3)

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

    # ── BASIC ─────────────────────────────────────────────
    with col_basic:
        is_current = current_plan == 'basic'
        can_upgrade = current_rank < PLAN_RANK['basic']
        st.markdown(
            f"### {_PLAN_DISPLAY['basic']['label']}"
            + (" ← *votre plan*" if is_current else "")
        )
        st.markdown(f"**{_PLAN_DISPLAY['basic']['price']}**")
        st.markdown("---")
        # Show free features first, then basic additions
        for feat in _feature_list('free'):
            st.markdown(f"✅ {feat}")
        basic_extras = sorted(
            PLAN_FEATURES['basic'] - PLAN_FEATURES['free']
        )
        for key in basic_extras:
            st.markdown(f"✅ {_PAGE_LABELS.get(key, key)}")
        st.markdown("---")
        if is_current:
            st.success("Plan actuel")
        elif can_upgrade:
            st.link_button("Passer à Basic →", "/?page=billing", type="primary")

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
