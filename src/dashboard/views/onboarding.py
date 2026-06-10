"""Post-register onboarding wizard — 3-step setup guide.

Type: Feature
Uses: get_db_connection, get_artist_id, get_artist_plan, PLAN_FEATURES
Depends on: artist_credentials table, saas_artists table
Accessible via /?page=onboarding (authenticated route).
"""
import streamlit as st

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.i18n import t
from src.dashboard.auth import get_artist_id, get_artist_plan
from src.database.stripe_schema import PLAN_FEATURES


# Platforms and which plan they require — all platform connectors are Free-tier.
_PLATFORM_META = {
    'spotify':    {'label': 'Spotify API',  'plan': 'free', 'icon': '🎵'},
    'youtube':    {'label': 'YouTube',       'plan': 'free', 'icon': '🎬'},
    'meta':       {'label': 'Meta Ads',      'plan': 'free', 'icon': '📱'},
    'instagram':  {'label': 'Instagram',     'plan': 'free', 'icon': '📸'},
    'soundcloud': {'label': 'SoundCloud',    'plan': 'free', 'icon': '☁️'},
    'apple_music':{'label': 'Apple Music',   'plan': 'free', 'icon': '🎎'},
}

_STEP_KEY = '_onboarding_step'


def _get_configured_platforms(artist_id: int) -> set[str]:
    """Return set of platforms that have at least token_encrypted or extra_config set."""
    db = get_db_connection()
    if db is None or artist_id is None:
        return set()
    try:
        rows = db.fetch_query(
            "SELECT platform FROM artist_credentials "
            "WHERE artist_id = %s AND (token_encrypted IS NOT NULL OR extra_config IS NOT NULL)",
            (artist_id,),
        )
        return {r[0] for r in rows}
    except Exception:
        return set()
    finally:
        db.close()


def _step_welcome(plan: str) -> None:
    st.title(t("onboarding.welcome_title", "🎵 Bienvenue sur Music Dashboard !"))
    st.markdown(
        t("onboarding.welcome_body",
          "Votre compte a été créé avec le plan **{plan}**. "
          "Voici ce qui est inclus dans votre plan actuel :").format(plan=plan.capitalize())
    )

    accessible = PLAN_FEATURES.get(plan, set())
    is_all = '*' in accessible

    col_free, col_premium = st.columns(2)

    plan_data = [
        ('free',    'Free',    [t("nav.item.home", "🏠 Accueil"), '🎵 Spotify & S4A', '🎬 YouTube',
                                '📱 Meta Ads', '📸 Instagram', '☁️ SoundCloud',
                                '🎎 Apple Music', '💰 iMusician',
                                t("nav.item.upload_csv", "📂 Import CSV"),
                                t("nav.item.export_pdf", "📄 Export PDF"), '🎁 Data Wrapped']),
        ('premium', 'Premium', ['+ 🚀 Road to Algo (ML)',
                                t("onboarding.feat_revenue", "+ 📈 Prévisions revenus"),
                                '+ 🔀 META x Spotify',
                                t("onboarding.feat_creatives", "+ 🎨 Créatives & CPR Meta")]),
    ]

    plan_ranks = {'free': 0, 'premium': 1}
    current_rank = plan_ranks.get(plan, 0)

    for col, (tier_key, tier_label, features) in zip(
        [col_free, col_premium], plan_data
    ):
        with col:
            tier_rank = plan_ranks[tier_key]
            is_current = tier_key == plan
            is_locked = tier_rank > current_rank and not is_all

            header = f"**{tier_label}**"
            if is_current:
                header += t("onboarding.your_plan", " ← *votre plan*")
            st.markdown(header)

            for feat in features:
                icon = "✅" if not is_locked or tier_rank <= current_rank else "🔒"
                st.markdown(f"{icon} {feat}")

            if is_locked:
                st.link_button(t("onboarding.upgrade_to", "Passer à {tier} →").format(tier=tier_label),
                               "/?page=billing")

    st.markdown("---")
    if st.button(t("onboarding.next_data", "Suivant : Configurer mes données →"), type="primary"):
        st.session_state[_STEP_KEY] = 2
        st.rerun()


def _step_credentials(plan: str, artist_id: int) -> None:
    st.title(t("onboarding.creds_title", "🔑 Configurer vos sources de données"))
    st.markdown(
        t("onboarding.creds_body",
          "Connectez vos plateformes pour commencer à collecter des données. "
          "Vous pouvez compléter cette étape plus tard depuis **Credentials API**.")
    )
    st.markdown("---")

    configured = _get_configured_platforms(artist_id)
    accessible = PLAN_FEATURES.get(plan, set())
    is_all = '*' in accessible

    plan_ranks = {'free': 0, 'premium': 1}
    current_rank = plan_ranks.get(plan, 0)

    for platform_key, meta in _PLATFORM_META.items():
        required_rank = plan_ranks.get(meta['plan'], 0)
        is_accessible = is_all or required_rank <= current_rank

        connected = platform_key in configured
        status = t("onboarding.connected", "✅ Connecté") if connected \
            else t("onboarding.not_configured", "❌ Non configuré")

        if is_accessible:
            cols = st.columns([3, 1, 1])
            cols[0].markdown(f"{meta['icon']} **{meta['label']}** — {status}")
            if not connected:
                cols[1].link_button(t("onboarding.configure_btn", "Configurer →"), "/?page=credentials")
        else:
            st.markdown(
                t("onboarding.locked_platform",
                  "🔒 {icon} **{label}** — *Disponible en plan {plan}*").format(
                      icon=meta['icon'], label=meta['label'], plan=meta['plan'].capitalize())
            )

    st.markdown("---")
    col_back, col_next = st.columns([1, 3])
    if col_back.button(t("onboarding.back", "← Retour")):
        st.session_state[_STEP_KEY] = 1
        st.rerun()
    if col_next.button(t("onboarding.next_finish", "Suivant : Terminer →"), type="primary"):
        st.session_state[_STEP_KEY] = 3
        st.rerun()


def _step_ready() -> None:
    st.title(t("onboarding.ready_title", "🎉 C'est parti !"))
    st.success(
        t("onboarding.ready_body",
          "Votre tableau de bord est prêt. Vous pouvez configurer vos credentials "
          "à tout moment depuis **Credentials API** dans la navigation.")
    )
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.link_button(t("onboarding.go_dashboard", "🏠 Aller au dashboard →"),
                       "/?page=home", type="primary")
    with col2:
        st.link_button(t("onboarding.configure_creds", "🔑 Configurer les credentials"),
                       "/?page=credentials")

    st.markdown("---")
    st.caption(
        t("onboarding.tip",
          "💡 Astuce : Lancez la collecte de données depuis le bouton "
          "**Lancer TOUTES les collectes** dans la barre latérale.")
    )


def show() -> None:
    if _STEP_KEY not in st.session_state:
        st.session_state[_STEP_KEY] = 1

    step = st.session_state[_STEP_KEY]
    plan = get_artist_plan()
    artist_id = get_artist_id()

    # Step progress indicator
    steps = [
        t("onboarding.step1", "1. Bienvenue"),
        t("onboarding.step2", "2. Données"),
        t("onboarding.step3", "3. Prêt !"),
    ]
    st.sidebar.markdown(t("onboarding.steps_header", "### Étapes"))
    for i, label in enumerate(steps, 1):
        prefix = "✅" if i < step else ("▶️" if i == step else "⬜")
        st.sidebar.markdown(f"{prefix} {label}")

    if step == 1:
        _step_welcome(plan)
    elif step == 2:
        _step_credentials(plan, artist_id)
    else:
        _step_ready()
