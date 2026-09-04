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
from src.dashboard.utils.tz import to_local_datetime
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


def _trial_deadline(artist_id: int | None, db) -> str | None:
    """La date de fin de l'essai premium, ou None. Jamais d'exception.

    `_grant_welcome_trial` pose `promo_plan_expires_at` à la création du compte. Rien
    ne le disait à l'artiste : il lisait « votre compte a été créé avec le plan
    Premium » et en déduisait que c'était acquis. Signalé en test le 2026-08-30.

    Prend la connexion de `show()` : elle ouvrait la sienne via `project_db()`, ce qui
    faisait DEUX connexions par rendu dès que `show()` a eu besoin de lire l'état de
    configuration. Attrapé par `tests/test_a_render_opens_one_connection.py`, qui
    compte à l'exécution — le compteur textuel, lui, ne voit pas `project_db()`.
    """
    if artist_id is None or db is None:
        return None
    try:
        row = db.fetch_query(
            "SELECT promo_plan_expires_at FROM saas_artists WHERE id = %s",
            (artist_id,))
        if row and row[0][0]:
            return to_local_datetime(row[0][0]).strftime("%d/%m/%Y")
    except Exception:  # noqa: BLE001 — une date manquante n'empêche pas l'onboarding
        return None
    return None


def _setup_roadmap() -> None:
    """The journey ahead, with the time it actually costs.

    Field note, 2026-08-30: the artist asked to see the roadmap *and its estimated
    time* on the welcome step. Two things make this block honest rather than
    decorative:

    - the minutes are COMPUTED from `total_effort(RECOMMENDED)`, never typed here.
      A hand-written duration is a number that stops being true the day a platform's
      `effort_min` changes, and nothing would notice. The per-platform matrix on the
      next step reads the same field, so the two can no longer disagree.
    - it names the exit ("tu peux t'arrêter après la première"), because the artist
      who reads a total and has less time will otherwise close the tab instead of doing one.
    """
    mins = total_effort(RECOMMENDED)
    names = ", ".join(BY_KEY[k].label for k in RECOMMENDED if k in BY_KEY)
    st.markdown("### " + t("onboarding.roadmap_title", "🗺️ Ta mise en route"))
    st.markdown(t(
        "onboarding.roadmap_body",
        "**1. Tu choisis tes plateformes** · ≈1 min\n"
        "→ à l'étape suivante, tu coches ce que tu veux brancher.\n\n"
        "**2. Tu saisis tes identifiants** · ≈{mins} min pour les deux "
        "recommandées ({names})\n"
        "→ chaque plateforme a son guide illustré, dans l'onglet Credentials API.\n\n"
        "**3. La collecte tourne cette nuit** · 0 min\n"
        "→ tes premiers graphiques sont là demain matin, puis chaque jour."
    ).format(mins=mins, names=names))
    st.caption(t(
        "onboarding.roadmap_partial",
        "Tu peux t'arrêter après une seule plateforme et revenir quand tu veux — "
        "rien n'est perdu, et chaque plateforme ajoutée enrichit les autres."))


def _step_welcome(plan: str, db) -> None:
    st.title(t("onboarding.welcome_title", "🎵 Bienvenue sur streaMLytics !"))

    # « streaMLytics en bref » — demandé après le test du 2026-08-30. Un artiste qui
    # vient de créer son compte sait ce qu'il a acheté ; il ne sait pas encore ce que
    # l'outil FAIT. Trois phrases, avant l'offre et avant le guide.
    st.markdown(t(
        "onboarding.in_brief",
        "#### streaMLytics en bref\n\n"
        "**1. Toutes tes données au même endroit, récupérées chaque jour, "
        "automatiquement** — Spotify, Instagram, Meta Ads, YouTube, SoundCloud, "
        "Apple Music. Tes identifiants sont chiffrés ; tu ne ressaisis rien.\n\n"
        "**2. La prédiction des algorithmes Spotify** — quand un titre a des chances "
        "de déclencher Discover Weekly ou Release Radar, et combien d'écoutes en "
        "attendre, via des modèles de machine learning entraînés sur tes données.\n\n"
        "**3. L'optimisation de tes campagnes** — en reliant ce que tu dépenses en "
        "promo à ce que ça produit réellement en écoutes."
    ))
    st.markdown("---")

    # L'offre, avec sa DURÉE et son échéance. Un essai dont on ne dit pas qu'il est un
    # essai n'est pas une offre, c'est une surprise à J+30.
    deadline = _trial_deadline(st.session_state.get("artist_id"), db)
    if plan == "premium" and deadline:
        st.success(t(
            "onboarding.trial_offer",
            "🎁 **Offre de bienvenue — Premium offert pendant 30 jours**, "
            "jusqu'au **{date}**.\n\n"
            "Ensuite ton compte repasse en **Free** : tu gardes tes données, tes "
            "connexions et tes exports. Tu perds **🚀 Road to Algo** (les prédictions "
            "de déclenchement Discover Weekly), les **prévisions de revenus** et les "
            "**analyses croisées Meta × Spotify**."
        ).format(date=deadline))
    else:
        st.markdown(
            t("onboarding.welcome_body",
              "Votre compte a été créé avec le plan **{plan}**. "
              "Voici ce qui est inclus dans votre plan actuel :").format(plan=plan.capitalize())
        )

    # Le guide. Il n'existait qu'en pièce jointe : e-mail perdu, guide perdu (R50).
    # Mis en avant et centré parce qu'un artiste en test ne l'a pas vu — c'est la
    # seule action de cette étape, elle doit se lire comme telle.
    _pdf = _guide_pdf_bytes(get_lang())
    if _pdf:
        st.markdown("### :orange-background["
                    + t("onboarding.guide_cta", "📄 Ton guide de démarrage") + "]")
        st.caption(t(
            "onboarding.guide_also_mailed",
            "Tu l'as aussi reçu en pièce jointe de l'e-mail de bienvenue — "
            "le voici si tu préfères le récupérer ici."))
        _c1, _c2, _c3 = st.columns([1, 2, 1])
        with _c2:
            st.download_button(
                t("onboarding.download_guide",
                  "📄 Télécharger le guide de mise en route (PDF)"),
                data=_pdf,
                file_name=f"streamlytics-guide-{get_lang()}.pdf",
                mime="application/pdf",
                use_container_width=True,
                type="primary",
            )
        st.markdown("---")

    _setup_roadmap()
    st.markdown("---")

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


def _step_credentials(plan: str, artist_id: int, db) -> None:
    st.title(t("onboarding.creds_title", "🔑 Par quoi veux-tu commencer ?"))
    # L'instruction « coche ce que tu veux » était ICI, au-dessus de la matrice
    # d'état — un artiste en test a essayé de cocher dans la matrice, où il n'y a
    # rien à cocher. Elle est descendue juste avant les vraies cases.

    # La connexion est celle de `show()`, ouverte une fois pour le rendu entier et
    # fermée par lui. Elle l'était ici, et refermée au milieu de l'étape : le bandeau
    # d'état ajouté au-dessus en aurait ouvert une seconde (règle transverse #9).
    configured = _get_configured_platforms(artist_id, db)

    if db is not None and artist_id is not None:
        st.markdown(t("onboarding.matrix_header",
                      "#### 📋 Où tu en es, plateforme par plateforme"))
        render_status_matrix(db, artist_id, key_suffix="onboarding")
        st.caption(t(
            "onboarding.matrix_legend",
            "🟢 vert = fait · ⚪ blanc = pas encore · 🔴 rouge = à corriger. "
            "**L'objectif : les trois colonnes vertes sur chaque plateforme que tu "
            "veux suivre.**\n\n"
            "**Configuré** : l'identifiant est saisi. **Répond** : la plateforme "
            "nous a bien répondu. **Données** : des chiffres sont arrivés."))
        st.markdown("---")

    accessible = PLAN_FEATURES.get(plan, set())
    is_all = '*' in accessible
    plan_ranks = {'free': 0, 'premium': 1}
    current_rank = plan_ranks.get(plan, 0)

    reco = [BY_KEY[k] for k in RECOMMENDED if k not in configured]
    if reco:
        st.info(t(
            "onboarding.reco_banner",
            "⭐ **Recommandé pour démarrer : {names}** — les plus rapides, {mins} min.\n\n"
            "La plus grosse valeur viendra ensuite du croisement **Meta Ads × import "
            "CSV Spotify for Artists** (différent de l'API Spotify) : c'est lui qui "
            "relie ce que tu dépenses en promo à ce que ça produit en écoutes."
        ).format(names=" + ".join(f"{p.icon} {p.label}" for p in reco),
                 mins=total_effort(p.key for p in reco)))

    st.markdown("---")

    # L'ACTION en gros, l'info en petit — demandé après le test du 2026-08-30 :
    # « mettre en gros gras surbrillance de section les ACTIONS à effectuer, en plus
    # petit les infos ».
    # ACTION → surbrillance. Voir le commentaire de `_render_platform_tab` sur le
    # choix de `:orange-background[…]` plutôt qu'un `<style>`.
    st.markdown("### :orange-background["
                + t("onboarding.pick_action", "👉 Coche ce que tu veux configurer maintenant")
                + "]")
    st.caption(t("onboarding.pick_hint",
                 "Tu n'as pas besoin de tout connecter. Le reste attendra dans "
                 "l'onglet **Credentials API**, plus tard, dans l'application."))

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


def _step_labels() -> list[str]:
    return [
        t("onboarding.step1", "1. Bienvenue"),
        t("onboarding.step2", "2. Données"),
        t("onboarding.step3", "3. Prêt !"),
    ]


def render_sidebar_steps() -> None:
    """Les trois étapes, EN HAUT de la barre latérale, et cliquables.

    Deux défauts en un, tous deux rapportés depuis une vraie deuxième connexion le
    2026-09-04.

    **La position.** Ce bloc vivait dans `show()`, donc il s'écrivait pendant la phase
    de CONTENU — après le logo, la langue, le menu et le bouton de déconnexion. Il
    atterrissait sous tout le reste : « c'est tout en bas du volet de navigation ».
    `app._main_body` l'appelle maintenant depuis la phase BARRE LATÉRALE, ce qui a
    demandé de séparer « quelle est la page ? » de « dessine le menu ».

    **L'atteignabilité.** Les trois lignes étaient du `st.markdown` : elles NOMMAIENT
    les étapes sans y mener — « impossible de revenir aux différentes étapes de
    config ». Même forme que les quatre étapes de l'accueil, corrigées le 2026-08-30
    pour la même raison. L'étape courante reste du texte : il n'y a rien à y aller.
    """
    if _STEP_KEY not in st.session_state:
        st.session_state[_STEP_KEY] = 1
    step = st.session_state[_STEP_KEY]

    st.sidebar.markdown(t("onboarding.steps_header", "### Étapes"))
    for i, label in enumerate(_step_labels(), 1):
        prefix = "✅" if i < step else ("▶️" if i == step else "⬜")
        if i == step:
            st.sidebar.markdown(f"**{prefix} {label}**")
        elif st.sidebar.button(f"{prefix} {label}", key=f"_onb_jump_{i}",
                               use_container_width=True):
            st.session_state[_STEP_KEY] = i
            st.rerun()
    st.sidebar.markdown("---")


def _render_landing_choice(db, state) -> None:
    """La sortie, et le droit de ne plus revenir.

    Demandé le 2026-09-04 : « un gros bouton d'accès à l'app si on le souhaite avec
    case à cocher qui nous dit qu'on souhaite garder cette page de connexion au début
    ou non ». Les deux comptent, et pour la même raison : l'assistant redevient
    l'atterrissage tant que la configuration n'est pas finie, ce qui n'est utile que si
    on peut le traverser **et** le désactiver. Un écran qu'on ne peut pas quitter n'est
    pas une aide, c'est une porte.

    L'écriture est synchrone, pas dans un `on_change` : le callback tournerait au début
    du run SUIVANT, quand la connexion de `show()` est déjà fermée.
    """
    from src.dashboard.utils.setup_completion import set_show_on_login

    if state.complete:
        st.success(t("onboarding.setup_complete",
                     "✅ Ta configuration est complète ({done}/{total}). "
                     "Cette page ne s'affichera plus à la connexion.")
                   .format(done=state.done_count, total=state.total))
    else:
        st.progress(state.done_count / state.total if state.total else 0.0)
        st.caption(t("onboarding.setup_progress",
                     "Configuration : **{done}/{total}** — tant que ce n'est pas "
                     "complet, tu retombes ici à la connexion.")
                   .format(done=state.done_count, total=state.total))

    col_go, col_keep = st.columns([2, 3])
    with col_go:
        if st.button(t("onboarding.enter_app", "🏠 Accéder à l'application →"),
                     type="primary", use_container_width=True, key="_onb_enter_app"):
            _goto('home')
    with col_keep:
        keep = st.checkbox(
            t("onboarding.keep_landing",
              "Afficher cette page à la connexion tant que ma configuration "
              "n'est pas terminée"),
            value=state.show_on_login, key="_onb_keep_landing")
        user_id = st.session_state.get('user_id')
        if keep != state.show_on_login and user_id and db is not None:
            try:
                set_show_on_login(db, user_id, keep)
            except Exception as exc:      # noqa: BLE001 — une préférence, jamais un mur
                logger.warning("show_setup_on_login not saved: %s", type(exc).__name__)
                st.caption(t("onboarding.keep_landing_unsaved",
                             "⚠️ Préférence non enregistrée — réessaie plus tard."))
    st.markdown("---")


def show() -> None:
    if _STEP_KEY not in st.session_state:
        st.session_state[_STEP_KEY] = 1

    step = st.session_state[_STEP_KEY]
    plan = get_artist_plan()
    artist_id = tenant_scope()

    # Une seule connexion pour tout le rendu — l'état de configuration, la matrice et
    # la liste de cases posent la même question à la même base (règle transverse #9).
    db = get_db_connection()
    try:
        from src.dashboard.utils.setup_completion import read_setup_state
        state = read_setup_state(db, artist_id, st.session_state.get('user_id'))
        if state.steps:
            _render_landing_choice(db, state)

        if step == 1:
            _step_welcome(plan, db)
        elif step == 2:
            _step_credentials(plan, artist_id, db)
        else:
            _step_ready()
    finally:
        if db is not None:
            db.close()
