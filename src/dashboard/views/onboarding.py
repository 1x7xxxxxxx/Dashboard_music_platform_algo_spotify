"""Post-register onboarding wizard — 3-step setup guide.

Type: Feature
Uses: get_db_connection, get_artist_id, get_artist_plan, PLAN_FEATURES
Depends on: artist_credentials table, saas_artists table
Accessible via /?page=onboarding (authenticated route).
"""
import json
import logging

import streamlit as st

logger = logging.getLogger(__name__)

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.guide_assets import credentials_guide_pdf
from src.utils.tenant_identity import declared_identities
from src.dashboard.utils.i18n import get_lang, t
from src.dashboard.auth import tenant_scope, get_artist_plan
from src.database.stripe_schema import PLAN_FEATURES
from src.dashboard.content.platform_value import (
    BY_KEY, RECOMMENDED, ordered_for_setup, total_effort,
)
from src.dashboard.utils.setup_focus import FOCUS_KEY
from src.dashboard.utils.status_matrix import render_status_matrix
from src.dashboard.utils.navigation import goto


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


def _goto(page_key: str) -> None:
    """Délègue à `utils.navigation.goto` — une seule règle de navigation dans l'app.

    Cette fonction portait sa propre copie ; l'accueil en a eu besoin le 2026-08-23 et
    recopier la règle une deuxième fois l'aurait laissée diverger. La version partagée
    fait en plus ce que celle-ci oubliait : désélectionner les radios de section, sans
    quoi le menu reste sur l'entrée précédente pendant que la page a changé.
    """
    goto(page_key)


def _get_configured_platforms(artist_id: int, db) -> set[str]:
    """Platforms the artist has actually connected.

    "Connected" means an IDENTITY was declared, not that a row exists: a tab opened
    and saved blank left a row behind and counted as connected here while the
    readiness matrix said ⚪. Instagram has no row of its own — it rides the `meta`
    row via `ig_user_id` — and the registry knows that, so this no longer restates it.

    The caller owns the connection and hands it in. This view is capped at ONE
    opened connection by `tests/test_view_connection_budget.py` — a textual count —
    and `_step_credentials` needs the same one for the status matrix.
    """
    if db is None or artist_id is None:
        return set()
    try:
        rows = db.fetch_query(
            "SELECT platform, extra_config FROM artist_credentials "
            "WHERE artist_id = %s AND (token_encrypted IS NOT NULL OR extra_config IS NOT NULL)",
            (artist_id,),
        )
        extra_by_platform = {}
        for platform, extra in rows:
            if isinstance(extra, str):
                try:
                    extra = json.loads(extra)
                except ValueError:
                    extra = {}
            extra_by_platform[platform] = extra if isinstance(extra, dict) else {}
        return declared_identities(extra_by_platform)
    except Exception as e:
        # NOT a silent `return set()`: a DB error and "this artist has connected
        # nothing" are different facts, and rendering the first as the second
        # tells an artist who configured everything that they configured nothing.
        st.warning(t(
            "onboarding.status_unavailable",
            "⚠️ Impossible de lire l'état de tes connexions ({err}). La liste "
            "ci-dessous peut afficher « non connecté » à tort — réessaie dans un "
            "instant avant de tout reconfigurer."
        ).format(err=type(e).__name__))
        return set()


def _guide_pdf_bytes(lang: str) -> bytes | None:
    """The onboarding guide as bytes, or None when it cannot be produced here.

    R50: the guide existed ONLY as an attachment to the welcome e-mail. Mail closed,
    guide gone — the same shape as the wizard that was itself reachable only from a
    link in that mail. A document a person cannot fetch again is one they have lost.

    Prefers the copy already rendered under `docs/guides/` and only renders when it is
    absent: WeasyPrint is slow enough to be felt inside a Streamlit rerun, and it is an
    optional dependency in some containers. A missing one must degrade to "no button",
    never to a traceback on a new artist's first screen.

    That reasoning now lives in `utils/guide_assets.py` and is CACHED there. It used to
    live only here, and `process_guide.py` — written the same day, for the same reason,
    calling the same builder — rebuilt the PDF on every rerun for 573 ms. One lesson
    held in one place is the only shape that stops the second caller from re-deriving it.
    """
    return credentials_guide_pdf(lang)


def _step_welcome(plan: str) -> None:
    st.title(t("onboarding.welcome_title", "🎵 Bienvenue sur streaMLytics !"))
    st.markdown(
        t("onboarding.welcome_body",
          "Votre compte a été créé avec le plan **{plan}**. "
          "Voici ce qui est inclus dans votre plan actuel :").format(plan=plan.capitalize())
    )

    # The guide, fetchable. It shipped only as an e-mail attachment, so an artist who
    # lost that mail had no way back to it (R50).
    _pdf = _guide_pdf_bytes(get_lang())
    if _pdf:
        st.download_button(
            t("onboarding.download_guide",
              "📄 Télécharger le guide de mise en route (PDF)"),
            data=_pdf,
            file_name=f"streamlytics-guide-{get_lang()}.pdf",
            mime="application/pdf",
            use_container_width=True,
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
                if st.button(t("onboarding.upgrade_to", "Passer à {tier} →").format(tier=tier_label),
                             key=f"_onb_upgrade_{tier_key}"):
                    _goto('billing')

    st.markdown("---")
    if st.button(t("onboarding.next_data", "Suivant : Configurer mes données →"), type="primary"):
        st.session_state[_STEP_KEY] = 2
        st.rerun()


def _step_credentials(plan: str, artist_id: int) -> None:
    st.title(t("onboarding.creds_title", "🔑 Par quoi veux-tu commencer ?"))
    st.markdown(
        t("onboarding.creds_body",
          "**Tu n'as pas besoin de tout connecter.** Coche ce que tu veux configurer "
          "maintenant — le reste attendra dans **Credentials API**.")
    )

    # One connection for the whole step: the matrix and the checkbox list ask the
    # same database about the same tenant.
    db = get_db_connection()
    configured = _get_configured_platforms(artist_id, db)

    if db is not None and artist_id is not None:
        st.markdown(t("onboarding.matrix_header",
                      "#### 📋 Où tu en es, plateforme par plateforme"))
        render_status_matrix(db, artist_id, key_suffix="onboarding")
        st.caption(t(
            "onboarding.matrix_legend",
            "**Configuré** : l'identifiant est saisi. **Répond** : la plateforme "
            "nous a bien répondu. **Données** : des chiffres sont arrivés."))
        st.markdown("---")
    if db is not None:
        db.close()

    accessible = PLAN_FEATURES.get(plan, set())
    is_all = '*' in accessible
    plan_ranks = {'free': 0, 'premium': 1}
    current_rank = plan_ranks.get(plan, 0)

    reco = [BY_KEY[k] for k in RECOMMENDED if k not in configured]
    if reco:
        st.info(t(
            "onboarding.reco_banner",
            "⭐ **Recommandé pour démarrer : {names}** — en {mins} min tu vois d'où "
            "viennent tes écoutes *et* si ton audience suit. C'est le couple qui "
            "permet de décider quelque chose ; le reste affine."
        ).format(names=" + ".join(f"{p.icon} {p.label}" for p in reco),
                 mins=total_effort(p.key for p in reco)))

    st.markdown("---")

    selection: list[str] = []
    for pv in ordered_for_setup(configured):
        meta = _PLATFORM_META.get(pv.key, {})
        required_rank = plan_ranks.get(meta.get('plan', 'free'), 0)
        if not (is_all or required_rank <= current_rank):
            st.markdown(
                t("onboarding.locked_platform",
                  "🔒 {icon} **{label}** — *Disponible en plan {plan}*").format(
                      icon=pv.icon, label=pv.label,
                      plan=meta.get('plan', 'free').capitalize())
            )
            continue

        connected = pv.key in configured
        head = f"{pv.icon} **{pv.label}**"
        if connected:
            head += t("onboarding.already_connected", " — ✅ déjà connecté")
        elif pv.recommended:
            head += t("onboarding.reco_tag", " — ⭐ recommandé")
        head += t("onboarding.effort", " · ≈{mins} min").format(mins=pv.effort_min)

        checked = st.checkbox(head, value=(pv.recommended and not connected),
                              disabled=connected, key=f"_onb_pick_{pv.key}")
        if checked and not connected:
            selection.append(pv.key)
        # The value line is what makes the checkbox answerable: an artist cannot
        # prioritise a platform name, only what it tells them.
        st.caption(t(f"onboarding.value.{pv.key}", pv.value))
        st.caption(t("onboarding.need", "À fournir : {need}").format(need=pv.need))
        if pv.caveat and not connected:
            st.caption(t(f"onboarding.caveat.{pv.key}", "⚠️ {c}").format(c=pv.caveat))
        st.markdown("")

    st.markdown("---")
    col_back, col_next = st.columns([1, 3])
    if col_back.button(t("onboarding.back", "← Retour")):
        st.session_state[_STEP_KEY] = 1
        st.rerun()

    if selection:
        label = t("onboarding.configure_selection",
                  "Configurer ma sélection ({n}) → ≈{mins} min").format(
                      n=len(selection), mins=total_effort(selection))
    else:
        label = t("onboarding.next_finish", "Continuer sans rien connecter →")
    if col_next.button(label, type="primary"):
        # Carried to the credentials page, which walks the selection in order and
        # tracks what is left — so "I picked two things" survives the navigation.
        st.session_state[FOCUS_KEY] = selection
        st.session_state[_STEP_KEY] = 3
        st.rerun()


def _step_ready() -> None:
    focus = st.session_state.get(FOCUS_KEY) or []
    st.title(t("onboarding.ready_title", "🎉 C'est parti !"))

    if focus:
        names = " + ".join(f"{BY_KEY[k].icon} {BY_KEY[k].label}" for k in focus if k in BY_KEY)
        st.success(
            t("onboarding.ready_focus",
              "Ta sélection : **{names}** (≈{mins} min). La page Credentials t'attend "
              "avec le guide de chacune — et te dira si la connexion ramène "
              "vraiment des données.").format(names=names, mins=total_effort(focus))
        )
    else:
        st.success(
            t("onboarding.ready_body",
              "Votre tableau de bord est prêt. Vous pouvez configurer vos credentials "
              "à tout moment depuis **Credentials API** dans la navigation.")
        )
    st.markdown("---")

    col1, col2 = st.columns(2)
    # The primary button follows the choice: someone who picked platforms wants the
    # form, not the (still empty) dashboard.
    if focus:
        with col1:
            if st.button(t("onboarding.go_configure", "🔑 Connecter ma sélection →"),
                         type="primary", key="_onb_done_creds"):
                _goto('credentials')
        with col2:
            if st.button(t("onboarding.go_dashboard", "🏠 Aller au dashboard →"),
                         key="_onb_done_home"):
                _goto('home')
    else:
        with col1:
            if st.button(t("onboarding.go_dashboard", "🏠 Aller au dashboard →"),
                         type="primary", key="_onb_done_home"):
                _goto('home')
        with col2:
            if st.button(t("onboarding.configure_creds", "🔑 Configurer les credentials"),
                         key="_onb_done_creds"):
                _goto('credentials')

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
    artist_id = tenant_scope()

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
