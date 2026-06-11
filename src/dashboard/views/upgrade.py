"""Plan comparison paywall page — shown when a locked feature is clicked.

Type: Feature
Uses: get_artist_plan, PLAN_FEATURES, PLAN_RANK
Depends on: billing view (Stripe portal CTA)
"""
import streamlit as st

from src.dashboard.auth import get_artist_plan
from src.dashboard.utils.i18n import t
from src.database.stripe_schema import (
    PLAN_CATALOG, PLAN_FEATURES, PLAN_RANK, SERVICE_CONTACT_EMAIL,
)


def _price_label(plan: str) -> str:
    p = PLAN_CATALOG[plan]['price_eur']
    if p == 0:
        return t("upgrade.price_free", "0€")
    return t("upgrade.price_monthly", "{p}€/mois").format(p=p)


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
    'sacem': '🎼 Royalties SACEM',
    'upload_csv': 'Import CSV',
    'credentials': 'Credentials API',
    'export_csv': 'Export CSV',
    'data_wrapped': 'Data Wrapped',
    'trigger_algo': '🚀 Road to Algo (ML)',
    'export_pdf': 'Export PDF',
    'revenue_forecast': 'Prévisions revenus',
    'meta_x_spotify': 'META x Spotify',
    'meta_mapping': 'Mapping cross-plateforme',
    'account': 'Mon compte',
    'billing': 'Billing',
}

_PLAN_DISPLAY = {
    'free':    {'label': 'Free',    'color': '#6c757d'},
    'premium': {'label': 'Premium', 'color': '#fd7e14'},
}


def _feature_list(plan: str) -> list[str]:
    """Return readable feature list for a given plan (premium = extras over Free)."""
    if plan == 'premium':
        return [
            t("upgrade.feat_road", "🚀 Road to Algo — prédictions ML"),
            t("upgrade.feat_forecast", "📈 Prévisions de revenus (ML)"),
            t("upgrade.feat_creatives", "🎨 Créatives Meta Ads"),
            '📊 CPR Optimizer',
            'META x Spotify',
            t("upgrade.feat_support", "Support prioritaire"),
        ]
    keys = PLAN_FEATURES.get(plan, set())
    return [t(f"upgrade.page.{k}", _PAGE_LABELS.get(k, k)) for k in sorted(keys)]


def show() -> None:
    current_plan = get_artist_plan()
    current_rank = PLAN_RANK.get(current_plan, 0)

    st.title(t("upgrade.title", "🔒 Passez à un plan supérieur"))
    st.caption(
        t("upgrade.caption",
          "Votre plan actuel : **{plan}**. "
          "Débloquez plus de fonctionnalités en upgradeant.").format(
              plan=_PLAN_DISPLAY[current_plan]['label'])
    )
    st.markdown("---")

    col_free, col_premium = st.columns(2)

    # ── FREE ──────────────────────────────────────────────
    with col_free:
        is_current = current_plan == 'free'
        st.markdown(
            f"### {_PLAN_DISPLAY['free']['label']}"
            + (t("upgrade.your_plan", " ← *votre plan*") if is_current else "")
        )
        st.markdown(f"**{_price_label('free')}**")
        st.markdown("---")
        for feat in _feature_list('free'):
            st.markdown(f"✅ {feat}")
        if is_current:
            st.success(t("upgrade.current_plan", "Plan actuel"))

    # ── PREMIUM ───────────────────────────────────────────
    with col_premium:
        is_current = current_plan == 'premium'
        can_upgrade = current_rank < PLAN_RANK['premium']
        st.markdown(
            f"### {_PLAN_DISPLAY['premium']['label']}"
            + (t("upgrade.your_plan", " ← *votre plan*") if is_current else "")
        )
        st.markdown(f"**{_price_label('premium')}**")
        st.markdown("---")
        st.markdown(t("upgrade.everything_free", "✅ **Tout le contenu Free, plus :**"))
        for feat in _feature_list('premium'):
            st.markdown(f"✅ {feat}")
        st.markdown("---")
        if is_current:
            st.success(t("upgrade.current_plan", "Plan actuel"))
        elif can_upgrade:
            st.link_button(t("upgrade.go_premium", "Passer à Premium →"),
                           "/?page=billing", type="primary")

    st.markdown("---")
    st.caption(
        t("upgrade.stripe_note",
          "Les paiements sont gérés via Stripe. "
          "Annulation possible à tout moment depuis la page Billing.")
    )
    st.markdown(
        t("upgrade.service_cta",
          "🎯 **Besoin qu'on optimise vos campagnes marketing pour vous ?** Service sur-mesure "
          "(appel préalable pour valider le fit + le budget) — 📧 [{email}]"
          "(mailto:{email}?subject=Optimisation%20campagnes%20-%20streaMLytics)").format(
              email=SERVICE_CONTACT_EMAIL)
    )
