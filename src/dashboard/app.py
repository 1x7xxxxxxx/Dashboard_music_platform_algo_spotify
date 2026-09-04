"""Application Streamlit principale avec déclenchement des DAGs."""
import warnings

# Harmless duplicate-matplotlib warning (Axes3D import) emitted transitively at import
# time — silenced before any view imports matplotlib/altair so it never reaches the UI/logs.
warnings.filterwarnings("ignore", message="Unable to import Axes3D")

import html as _html
import streamlit as st
from pathlib import Path
import sys
import time
from datetime import datetime
import os

# ✅ IMPORTANT : Ajouter le chemin AVANT les imports src.*
# resolve() → chemin absolu garanti, insert(0) → priorité maximale
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ...and this file's OWN directory, for the 44 `from views.<page> import show`
# routes below. That entry was never guaranteed here: it came for free from
# Streamlit's bootstrap (`sys.path.insert(0, dirname(abspath(main_script)))`),
# so every route depended on a third-party implementation detail that app.py
# never asserted. Any launcher that is not `streamlit run` — and a local run on
# 2026-08-30 22:34 produced exactly that — raises `ModuleNotFoundError: No
# module named 'views'` on the FIRST navigation, not at boot, so the app starts
# clean and dies on a click. Stating the guarantee costs three lines.
_dashboard_dir = str(Path(__file__).resolve().parent)
if _dashboard_dir not in sys.path:
    sys.path.insert(0, _dashboard_dir)

# Resolve .env from the repository root, NOT from the cwd: the documented launch is
# `cd src/dashboard && streamlit run app.py`, where the cwd-relative test below found
# neither file and load_dotenv() returned False without a word (measured 2026-08-21).
from src.utils.env_files import load_project_env  # noqa: E402

load_project_env()

from src.utils.config_loader import config_loader
from src.utils.airflow_trigger import AirflowTrigger
from src.dashboard.auth import (require_login, show_user_sidebar, get_artist_plan,
                                render_logout_footer)
from src.dashboard.utils.i18n import t, get_lang
from src.database.stripe_schema import PLAN_FEATURES, ALWAYS_ACCESSIBLE
from src.dashboard.utils.setup_completion import FIRST_RUN_FOCUS

st.set_page_config(page_title="streaMLytics", page_icon="🎵", layout="wide")

# Pandas 3.0 forward-compat: opt in now to the new fillna semantics so the
# 28+ `df[col].fillna(0).astype(...)` patterns across views don't emit
# FutureWarning and won't break silently when pandas 3 ships. The cast we
# do explicitly after fillna keeps the final dtype deterministic — only the
# intermediate silent downcasting is being disabled.
import pandas as pd
pd.set_option('future.no_silent_downcasting', True)

config = config_loader.load()
airflow_config = config.get('airflow', {})
# Env vars take precedence over config.yaml — required for Railway deployment
_airflow_pass = os.getenv('AIRFLOW_PASSWORD') or airflow_config.get('password')
if not _airflow_pass:
    raise RuntimeError(
        "AIRFLOW_PASSWORD not configured. Set it in .env or config/config.yaml. "
        "Never use a hardcoded default — it allows unauthenticated DAG triggering."
    )
# Fail loud at boot, not at the first credential save. Without FERNET_KEY every stored API
# credential is undecryptable and every connection test silently fails (the kind of silent
# gap the Benken session hit). Resolution mirrors _core._get_fernet (env → config.yaml).
if not (os.getenv('FERNET_KEY') or config.get('fernet_key')):
    raise RuntimeError(
        "FERNET_KEY not configured (env var or config/config.yaml `fernet_key`). Stored API "
        "credentials cannot be decrypted — credential saves and connection tests would "
        "silently fail. Generate one: python -c \"from cryptography.fernet import Fernet; "
        "print(Fernet.generate_key().decode())\""
    )
airflow_trigger = AirflowTrigger(
    base_url=os.getenv('AIRFLOW_BASE_URL', airflow_config.get('base_url', 'http://localhost:8080')),
    username=os.getenv('AIRFLOW_USERNAME', airflow_config.get('username', 'admin')),
    password=_airflow_pass,
)

def _verify_email(token: str) -> None:
    """Handle the email verification link (?page=verify&token=xxx)."""
    st.title(t("app.verify_title", "🎵 Vérification de l'email"))
    if not token:
        st.error(t("app.verify_invalid_link", "Lien de vérification invalide."))
        return
    from src.dashboard.utils import get_db_connection
    db = get_db_connection()
    if db is None:
        st.error(t("app.db_unreachable_short", "Base de données injoignable."))
        return
    try:
        rows = db.fetch_query(
            "SELECT id, username, email, email_verified, verification_token_created_at "
            "FROM saas_users "
            "WHERE verification_token = %s LIMIT 1",
            (token,)
        )
        if not rows:
            st.error(t("app.verify_used_link",
                       "Ce lien de vérification est invalide ou a déjà été utilisé."))
            return
        uid, username, email, already_verified, token_created_at = rows[0]
        if already_verified:
            st.info(t("app.verify_already",
                      "Le compte **{u}** est déjà vérifié.").format(u=username))
            # Même raison que le bouton du cas nominal, plus bas : un lien navigue,
            # un bouton relance la page. « [Se connecter](/) » au fil du texte
            # cumulait les deux défauts — il se rate à la lecture, et il peut ouvrir
            # un onglet.
            if st.button(t("app.verify_login_btn", "→ Me connecter"), type="primary",
                         key="_verify_goto_login_already"):
                st.query_params.clear()
                st.rerun()
            return
        # INFO-01: reject tokens older than 48 hours
        if token_created_at:
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            created = token_created_at if token_created_at.tzinfo else token_created_at.replace(tzinfo=timezone.utc)
            if now - created > timedelta(hours=48):
                db.execute_query(
                    "UPDATE saas_users SET verification_token = NULL, "
                    "verification_token_created_at = NULL WHERE id = %s",
                    (uid,)
                )
                st.error(t(
                    "app.verify_expired",
                    "Ce lien de vérification a expiré (48 heures). "
                    "Inscrivez-vous à nouveau ou utilisez l'option de renvoi sur la page "
                    "de connexion."
                ))
                return
        db.execute_query(
            "UPDATE saas_users SET email_verified = TRUE, verification_token = NULL, "
            "verification_token_created_at = NULL WHERE id = %s",
            (uid,)
        )
        # Show the confirmation FIRST — the verification is already committed above.
        # The welcome email (a blocking ~3s SMTP round-trip) must NOT delay the message
        # the user is waiting for; send it after the success is rendered.
        st.success(t(
            "app.verify_success",
            "✅ Email vérifié ! Bienvenue, **{u}**. "
            "Nous vous avons envoyé un guide de bienvenue par email."
        ).format(u=username))
        # Un BOUTON, pas un `st.link_button`. Signalé le 2026-09-04 : « ça m'ouvre une
        # nouvelle fenêtre, est-ce qu'on peut rester sur la même fenêtre ? »
        #
        # `st.link_button` rend une balise `<a>` : le navigateur navigue, et selon la
        # façon dont la page a été ouverte — depuis un client mail, typiquement — il
        # peut le faire dans un nouvel onglet. On ne contrôle pas ce choix.
        #
        # Un bouton Streamlit n'en pose pas : il efface le paramètre d'URL et relance
        # le script. Il n'y a aucune navigation HTML, donc aucun onglet possible. Le
        # même écran devient l'écran de connexion — c'est ce qu'un lien vers `/`
        # essayait d'obtenir.
        if st.button(t("app.verify_login_btn", "→ Me connecter"), type="primary",
                     key="_verify_goto_login"):
            st.query_params.clear()
            st.rerun()
        # Welcome email + onboarding guide PDF — sent now (account confirmed), NOT at
        # signup, so the guide lands only once the address is proven deliverable.
        try:
            from src.dashboard.views.register import WELCOME_TRIAL_DAYS
            from src.utils.verification_email import send_welcome_email
            with st.spinner(t("app.sending_welcome", "Envoi du guide de bienvenue…")):
                send_welcome_email(email, username, WELCOME_TRIAL_DAYS, user_id=uid,
                                   lang=get_lang())
        except Exception:
            pass  # best-effort — never block verification on the welcome email
    finally:
        db.close()


def _unsubscribe(uid: str, token: str, scope: str = "marketing") -> None:
    """Handle the one-click unsubscribe link (?page=unsubscribe&uid=&t=&scope=).

    Verifies the HMAC token, then sets marketing_consent=FALSE for that user — no
    login required. Mirrors the toggle in 'Mon compte → Communications'.
    """
    st.title(t("app.unsub_title", "📧 Désinscription"))
    from src.utils.verification_email import verify_unsubscribe_token
    try:
        user_id = int(uid)
    except (TypeError, ValueError):
        st.error(t("app.unsub_invalid", "Lien de désinscription invalide."))
        return
    if not verify_unsubscribe_token(user_id, token):
        st.error(t("app.unsub_expired", "Lien de désinscription invalide ou expiré."))
        return
    from src.dashboard.utils import get_db_connection
    db = get_db_connection()
    if db is None:
        st.error(t("app.db_unreachable_retry",
                   "Base de données injoignable. Réessayez plus tard."))
        return
    try:
        # One link, two scopes. `digest` stops the weekly recap ONLY: it is a service
        # e-mail for a paid feature, and clearing `marketing_consent` for it would
        # silently switch off every unrelated communication as well. Column names are
        # not interpolated — the branch is explicit, so there is no identifier to
        # validate against an allowlist (cross-cutting rule #8).
        if scope == "digest":
            db.execute_query(
                "UPDATE saas_users SET weekly_digest_optout_at = now() WHERE id = %s",
                (user_id,),
            )
            st.success(t(
                "app.unsub_digest_success",
                "✅ C'est fait — vous ne recevrez plus le récapitulatif hebdomadaire. "
                "Vos autres e-mails ne changent pas."
            ))
        else:
            db.execute_query(
                "UPDATE saas_users SET marketing_consent = FALSE, marketing_consent_at = now() "
                "WHERE id = %s",
                (user_id,),
            )
            st.success(t(
                "app.unsub_success",
                "✅ C'est fait — vous ne recevrez plus de communications marketing. "
                "Vous pouvez réactiver l'option à tout moment dans « Mon compte → Communications »."
            ))
    finally:
        db.close()


# Sidebar layout: ordered sections, each (stable_id, header_label, [(item_label, page_key), ...]).
# Order = user journey. Empty header = no visual separator (top entry).
_NAV_SECTIONS = [
    # Les exports étaient les entrées n°2 et n°3, AVANT le guide et les credentials —
    # on proposait d'exporter avant qu'il y ait quoi que ce soit à exporter, alors que
    # le commentaire ci-dessus annonce « Order = user journey ». Descendus après les
    # analytics, là où l'artiste a enfin quelque chose à emporter.
    ("start",     "",                       [("🏠 Accueil", "home")]),
    ("data",      "⚙️ Configuration de streaMLytics",             [("🚀 Mise en route (assistant)", "onboarding"),
                                             ("📋 Guide de démarrage", "process_guide"),
                                             ("🔑 Credentials API + imports CSV", "credentials"),
                                             # Juste APRÈS la saisie : on remplit,
                                             # puis on regarde où on en est. Sortie
                                             # de Credentials le 2026-09-04, où elle
                                             # poussait le champ à y=1475.
                                             ("📋 État de tes plateformes", "platform_status"),
                                             ("🔗 Mapping cross-plateforme", "meta_mapping"),
                                             ("🚦 Santé onboarding", "onboarding_health"),
                                             ("🗄️ Santé des données", "db_health")]),
    ("analytics", "📊 Analytics plateformes", [("🎵 Spotify + Spotify for Artists", "spotify_s4a_combined"),
                                             ("🎵 META x Spotify", "meta_x_spotify"),
                                             ("🎎 Apple Music", "apple_music"),
                                             ("🎬 YouTube", "youtube"),
                                             ("☁️ SoundCloud", "soundcloud"),
                                             ("📸 Instagram", "instagram"),
                                             ("📱 Hypeddit", "hypeddit"),
                                             # Data Wrapped vivait dans « Rapports &
                                             # exports », à côté des exports PDF/CSV.
                                             # Ce n'est pas un export : c'est une
                                             # lecture de ses chiffres, comme les six
                                             # entrées au-dessus. Déplacé le
                                             # 2026-09-04 à la demande de l'artiste.
                                             ("🎁 Data Wrapped", "data_wrapped")]),
    ("advanced",  "🔮 Prédiction algos Spotify", [("📝 Saisie S4A (playlist & Discovery)", "saisie_s4a"),
                                             ("🚀 Prédiction déclenchement algos Spotify (DW, Radio, RR…)", "trigger_algo")]),
    ("ads",       "📣 Publicité Meta Ads",  [("📱 Vue d'ensemble", "meta_ads_overview"),
                                             ("🎨 Visuels de campagne", "meta_creatives"),
                                             ("🌍 Qui a vu tes pubs (pays, âge, placement)", "meta_breakdowns"),
                                             ("📊 CPR Optimizer", "meta_cpr_optimizer")]),
    ("revenue",   "💶 Revenus",             [("💰 Distributeurs (iMusician, DistroKid…)", "imusician"),
                                             ("🎼 SACEM", "sacem"),
                                             ("📈 Prévisions revenus", "revenue_forecast")]),
    ("reports",   "🎁 Rapports & exports",  [("📄 Export PDF", "export_pdf"),
                                             ("⬇️ Export CSV", "export_csv")]),
    ("account",   "👤 Compte",              [("👤 Mon compte", "account"),
                                             ("💳 Billing", "billing"),
                                             ("🎁 Parrainage", "referral")]),
    ("admin",     "🛠️ Admin / Ops",        [("⚡ Perf. Dashboard", "perf_monitor"),
                                             ("📈 Usage Analytics", "usage_analytics"),
                                             ("🏗️ Monitoring ETL", "airflow_kpi"),
                                             ("🗂️ Historique ETL", "etl_logs"),
                                             ("🤖 Perf. Modèles ML", "ml_performance"),
                                             ("🚨 Alertes", "alerts"),
                                             ("📊 Referral KPIs", "referral_kpi"),
                                             ("🎟️ Promo Codes", "promo_admin"),
                                             ("🔧 Liens & Outils", "useful_links"),
                                             ("⚙️ Admin", "admin")]),
]
# Pages réservées admin (cachées pour le rôle 'artist')
_ADMIN_ONLY = {'airflow_kpi', 'admin', 'ml_performance', 'useful_links',
               'etl_logs', 'referral_kpi', 'promo_admin', 'perf_monitor',
               'usage_analytics', 'alerts'}


def _on_nav_select(skey: str, all_skeys: list):
    """Radio callback: keep a single active page across all section radios."""
    val = st.session_state.get(skey)
    if val is None:
        return  # deselection echo — ignore
    st.session_state['_nav_page'] = val
    for other in all_skeys:
        if other != skey:
            st.session_state[other] = None


def show_view_as_selector():
    """Admin-only QA: preview the app as Free / Premium / Admin without altering the
    real tenant. Drives nav role-gating + plan paywalls for the current session only —
    this previews ACCESS, not data isolation (data stays admin-wide)."""
    labels = {'admin': '🛠️ Admin (tout)', 'premium': '💎 Premium', 'free': '🆓 Free'}
    st.sidebar.markdown(t("nav.view_as_header", "###### 👁️ Voir comme (QA admin)"))
    st.sidebar.radio(
        "view_as",
        ['admin', 'premium', 'free'],
        key='_view_as',
        format_func=lambda k: labels[k],
        label_visibility="collapsed",
    )
    st.sidebar.caption(t("nav.view_as_help",
                         "Aperçu d'accès Free/Premium. Les données restent admin-wide."))
    st.sidebar.markdown("---")


def _setup_is_unfinished(role: str) -> bool:
    """Cette arrivée mérite-t-elle la mise en route ? (configuration non finie, non refusée)

    Tout le monde atterrissait sur `home` sans condition. Pour un artiste qui vient de
    s'inscrire, `home` est un tableau d'état vide : quatre tuiles à zéro et des cartes de
    fraîcheur qui n'ont rien à rafraîchir. Il ne dit pas quoi faire, et l'assistant qui le
    dirait n'était joignable que depuis l'e-mail de vérification.

    Le seuil a changé le 2026-09-04, et c'est le cœur du correctif. Il valait « l'artiste
    n'a-t-il **rien** branché ? » (`all(status == 'todo')`), donc une seule identité
    déclarée suffisait à faire disparaître l'assistant : la deuxième connexion tombait
    sur un accueil à 1/4, sans chemin de retour vers le reste de la configuration.
    Rapporté tel quel depuis un vrai deuxième login — « je ne suis plus sur étapes 1 2
    3 », « impossible de revenir aux différentes étapes de config ». La question est
    « a-t-il **fini** ? », et elle a une seule définition, dans
    `utils.setup_completion` — la même que l'accueil affiche en `{done}/4`.

    L'artiste garde la main : la case à cocher de l'assistant écrit
    `saas_users.show_setup_on_login`, et une configuration terminée rend la question
    sans objet.

    Ne se déclenche qu'à la PREMIÈRE évaluation de la session (`_nav_page` absent), donc
    un artiste qui navigue ensuite vers l'accueil y reste.

    Toute erreur — et toute lecture qui n'a rien rendu — retombe sur `home` : un
    aiguillage d'accueil ne doit jamais empêcher d'entrer dans l'application, et
    « je n'ai pas pu lire » n'est pas « il n'a pas fini ».
    """
    if role == 'admin':
        return False
    try:
        from src.dashboard.auth import get_artist_id
        artist_id = get_artist_id()
        if artist_id is None:
            return False
        from src.dashboard.utils import get_db_connection
        from src.dashboard.utils.setup_completion import read_setup_state
        db = get_db_connection()
        if db is None:
            return False
        try:
            state = read_setup_state(db, artist_id, st.session_state.get('user_id'))
        finally:
            db.close()
        if not state.steps or state.complete or not state.show_on_login:
            return False
        return True
    except Exception:      # noqa: BLE001 — jamais bloquer l'entrée dans l'app
        return False


_FIRST_RUN_EVALUATED = '_first_run_evaluated'


def arm_first_run_once(role: str) -> None:
    """Décide UNE fois par session si cette arrivée est une première connexion.

    Séparé de l'atterrissage le 2026-09-04, et c'est un correctif, pas un rangement.
    Le drapeau n'était posé que dans la branche de réparation de `resolve_nav_page`,
    qui ne se déclenche que si `_nav_page` est ABSENT de la session. Or le mail de
    bienvenue envoie sur `?page=onboarding`, et `_main_body` épingle ce paramètre
    AVANT : la page était donc déjà connue, la branche ne tournait pas, et l'artiste
    qui arrivait par le lien du mail — c'est-à-dire **le chemin nominal** — recevait le
    menu complet. Signalé tel quel : « normalement la première fois qu'on se connecte
    on n'a pas accès au volet de navigation, il faudrait le remettre ».

    La question « est-ce une première connexion ? » ne dépend pas de la façon dont la
    page a été choisie. Elle se pose donc ici, une fois par session, quel que soit le
    chemin d'entrée.
    """
    if st.session_state.get(_FIRST_RUN_EVALUATED):
        return
    st.session_state[_FIRST_RUN_EVALUATED] = True
    if _setup_is_unfinished(role):
        st.session_state[FIRST_RUN_FOCUS] = True


def _first_run_landing(role: str) -> str:
    """`onboarding` si cette arrivée est une première connexion, `home` sinon."""
    return 'onboarding' if st.session_state.get(FIRST_RUN_FOCUS) else 'home'


# Les pages qui font PARTIE de la mise en route. Le mode « première connexion » les
# traverse toutes ; il s'éteint sur la première page qui n'en est pas.
_SETUP_PAGES = frozenset({'onboarding', 'credentials', 'upload_csv', 'process_guide',
                          'platform_status'})

# Les pages qu'un LIEN a le droit d'imposer à une première arrivée. Ce n'est PAS
# `_SETUP_PAGES`, et les confondre était un défaut : un seul ensemble répondait à deux
# questions différentes —
#
#   « le mode première connexion survit-il à cette page ? »  → _SETUP_PAGES
#       (il traverse tout le parcours : Credentials, l'import CSV, l'état…)
#   « ce paramètre d'URL peut-il battre l'atterrissage ? »   → _LANDING_LINKS
#       (une seule page est visée par un lien réel : celui du mot de bienvenue)
#
# Signalé le 2026-09-04 : « je viens de me connecter avec le reset et je tombe
# directement sur la page Credentials API alors qu'on devrait tomber vers Mise en
# route ». L'URL portait encore `?page=credentials` de la session précédente ; comme
# Credentials appartient au parcours, elle était honorée. Aucun lien n'envoie
# pourtant personne là au premier jour — seul un onglet resté ouvert le fait.
_LANDING_LINKS = frozenset({'onboarding'})


def resolve_nav_page(role: str = 'artist'):
    """Decide the active page and repair nav state — WITHOUT drawing anything.

    Split out of `show_navigation_menu` on 2026-09-04 so that the sidebar can be built
    in the order a reader expects. The assistant's step list (`### Étapes`) is written
    by `views/onboarding.show()`, which runs in the CONTENT phase — i.e. after the
    whole sidebar — so it landed at the very bottom, under the logout button. Reported
    as « c'est tout en bas du volet de navigation ». Nothing can be placed above the
    navigation while the navigation is what computes the page.

    Returns `(page_key, rendered, all_skeys)`. Widgets are drawn by
    `render_navigation`; the page returned here is the raw key, plan-gating is applied
    at the end of the render.
    """
    arm_first_run_once(role)

    rendered = []  # list of (skey, header, [(label, key), ...])
    for sec_id, header, items in _NAV_SECTIONS:
        vis = [(lbl, key) for lbl, key in items
               if role == 'admin' or key not in _ADMIN_ONLY]
        if vis:
            rendered.append((f"_nav_{sec_id}", header, vis))

    all_skeys = [skey for skey, _, _ in rendered]
    visible_keys = {key for _, _, items in rendered for _, key in items}

    # Init / repair before any widget is instantiated (legal here, not after).
    # Triggers on first load OR when the active page is no longer visible
    # (role/plan change) — falls back to home.
    if st.session_state.get('_nav_page') not in visible_keys:
        landing = _first_run_landing(role) if '_nav_page' not in st.session_state else 'home'
        st.session_state['_nav_page'] = landing
        # `_nav_start` n'est PAS une clé d'état libre : c'est la clé du radio de la
        # section `start`, dont la seule option est `home`. La ligne retirée ici y
        # écrivait la page d'atterrissage — donc `onboarding`, une valeur que ce radio
        # n'offre pas. `navigation.py` la traitait d'ailleurs comme « pas une section ».
        # `_select_nav_radio` ci-dessous lui donne la seule valeur correcte.

    page = st.session_state.get('_nav_page', 'home')
    # Le mode « première connexion » couvre le PARCOURS de mise en route, pas la seule
    # page de l'assistant. Il ne durait qu'un écran : le bouton « Connecter ma
    # sélection » mène à Credentials, la page changeait, le drapeau tombait — et la
    # page qui doit justement se réduire aux plateformes cochées les affichait toutes
    # les six. Vérifié au navigateur le 2026-09-04.
    #
    # Il meurt dès que l'artiste est ailleurs que dans son installation : l'accueil ou
    # n'importe quelle vue d'analyse veut dire qu'il est entré dans l'application, et
    # y revenir plus tard par le menu doit la lui rendre entière.
    if page not in _SETUP_PAGES:
        st.session_state.pop(FIRST_RUN_FOCUS, None)
    # Toujours, pas seulement à la réparation. `utils.navigation.goto` remet toutes les
    # radios à `None` — le menu n'affichait donc AUCUNE sélection après un bouton
    # « Configurer les credentials », exactement comme à la première connexion. Réaffirmer
    # l'accord ici est idempotent : un clic dans le menu a déjà posé la bonne valeur.
    # Légal parce que ceci tourne AVANT que les radios soient instanciées.
    _select_nav_radio(page, rendered)
    return page, rendered, all_skeys


def _select_nav_radio(page_key: str, rendered) -> None:
    """Point the section radios at `page_key` — the one that owns it, and no other.

    Every radio was set to `None` here, which is why NOTHING was highlighted in the
    menu on a first connection: `_nav_page` said `onboarding`, the content rendered the
    assistant, and the sidebar showed no selection at all. Reported twice — « il n'y a
    toujours pas d'onglet sélectionné dans le navigateur quand on se connecte la
    première fois ». The page and the menu are the same fact; they must be written
    together.
    """
    for skey, _, items in rendered:
        keys = [key for _, key in items]
        st.session_state[skey] = page_key if page_key in keys else None


def _neighbour_pages(rendered, current: str, is_locked) -> tuple:
    """(page précédente, page suivante) dans l'ordre du menu — ou None de chaque côté.

    Les pages VERROUILLÉES sont sautées : une flèche est un geste d'exploration, et
    l'envoyer buter sur le paywall une entrée sur deux transforme l'exploration en
    parcours d'obstacles. Elles restent atteignables par le menu, avec leur 🔒, qui
    est le bon endroit pour proposer une montée en gamme — le clic y est délibéré.

    Pure : elle ne lit ni Streamlit ni la session, donc l'ordre se teste sans rendre
    une page.
    """
    order = [key for _, _, items in rendered for _, key in items
             if not is_locked(key)]
    if current not in order:
        return None, None
    i = order.index(current)
    return (order[i - 1] if i > 0 else None,
            order[i + 1] if i < len(order) - 1 else None)


def render_navigation(role: str, rendered, all_skeys) -> str:
    """Draw the section radios; return the page, plan-gating applied."""
    # Plan-based gating: locked pages shown with 🔒 and routed to upgrade view
    plan = get_artist_plan()
    accessible = PLAN_FEATURES.get(plan, set())
    is_all = '*' in accessible  # premium: unrestricted

    def _is_locked(key: str) -> bool:
        return not (is_all or key in ALWAYS_ACCESSIBLE or key in accessible)

    # Le titre, et deux flèches pour passer d'une page à la suivante sans chercher
    # dans une liste de quarante entrées. Demandé le 2026-09-04 : « rajoute 2 flèches
    # cliquables qui passent d'un onglet à l'autre à côté de NAVIGATION ».
    #
    # Écrire `_nav_page` ici est LÉGAL et ne l'est pas partout : on est dans la phase
    # barre latérale, avant que les radios de section soient instanciés — c'est
    # exactement la contrainte documentée dans `utils/navigation.py`. Le rerun qui
    # suit fait accorder le menu par `resolve_nav_page`.
    _cur = st.session_state.get('_nav_page', 'home')
    _prev, _next = _neighbour_pages(rendered, _cur, _is_locked)

    # `vertical_alignment="center"` et un `###` plutôt qu'un `st.title`.
    #
    # Un `st.title` mesure ~2,5 fois la hauteur d'un bouton et porte sa propre marge
    # haute ; les colonnes s'alignant par le HAUT, les deux flèches flottaient contre
    # le sommet du titre, très au-dessus de sa ligne de base. « Pas alignées avec
    # Navigation, c'est moche » — 2026-09-04, et c'est exact : rien ne les alignait.
    #
    # Deux corrections, pas une. L'alignement centre les trois colonnes sur la même
    # ligne médiane ; le titre passe en `###` pour que cette ligne médiane soit à peu
    # près la hauteur d'un bouton — centrer un titre trois fois trop haut aurait
    # laissé les flèches au milieu d'un grand vide.
    try:
        _c_title, _c_prev, _c_next = st.sidebar.columns(
            [5, 1, 1], vertical_alignment="center")
    except TypeError:      # Streamlit < 1.36 — pas d'alignement vertical
        _c_title, _c_prev, _c_next = st.sidebar.columns([5, 1, 1])
    # Le titre reçoit la HAUTEUR d'un bouton, et s'y centre lui-même.
    #
    # Mesuré au navigateur, parce que deux tentatives ont raté avant celle-ci. Un
    # `st.title` place les flèches ~25 px au-dessus de sa ligne de base (colonnes
    # alignées par le haut). `vertical_alignment="center"` + un `###` laisse encore
    # 8 px, et la mesure dit pourquoi : le conteneur `stMarkdown` du titre est haut
    # de **13 px** alors que le `<h3>` qu'il porte en fait **29** — le titre déborde
    # de la boîte que Streamlit centre. Mettre la marge à zéro n'y change rien : ce
    # n'est pas la marge qui est fausse, c'est la hauteur mesurée.
    #
    # On cesse donc de compenser et on égalise : une boîte de 40 px — la hauteur
    # d'un bouton Streamlit — qui centre son propre texte. Les deux colonnes ont
    # alors la même hauteur de contenu, et l'alignement est vrai quelle que soit la
    # façon dont Streamlit la calcule. C'est NOTRE balise, pas un `<style>` visant
    # ses classes internes (`st-emotion-cache-…` change sans prévenir).
    #
    # Le `-16px` est MESURÉ, et sa valeur a une raison qui vaut d'être écrite : à
    # hauteurs égales (40 px des deux côtés, Streamlit 1.54), le bloc de texte
    # commençait 8 px plus bas que le bouton. Une compensation de -8 px n'en a
    # rattrapé que 4 — `vertical_alignment="center"` recentre APRÈS la marge, donc
    # il en amortit la moitié. Il faut le double de l'écart observé.
    #
    # Pour le remesurer un jour : comparer `getBoundingClientRect()` du div ci-
    # dessous et d'une flèche, et mettre ici deux fois l'écart des centres. Trop
    # petit pour valoir un test — un test de pixels casse à chaque montée de
    # version et n'apprendrait rien de plus que l'œil.
    _c_title.markdown(
        '<div style="height:40px;margin-top:-16px;display:flex;align-items:center;'
        'font-size:1.25rem;font-weight:600;">'
        + _html.escape(t("nav.title", "🎵 Navigation")) + '</div>',
        unsafe_allow_html=True)
    from src.dashboard.utils.navigation import goto
    if _c_prev.button("◀", key="_nav_prev", disabled=_prev is None,
                      help=t("nav.prev", "Page précédente"),
                      use_container_width=True):
        goto(_prev)
    if _c_next.button("▶", key="_nav_next", disabled=_next is None,
                      help=t("nav.next", "Page suivante"),
                      use_container_width=True):
        goto(_next)

    label_by_key = {key: t(f"nav.item.{key}", lbl)
                    for _, _, items in rendered for lbl, key in items}

    def _fmt(key: str) -> str:
        return f"🔒 {label_by_key[key]}" if _is_locked(key) else label_by_key[key]

    for skey, header, items in rendered:
        if header:
            sec_id = skey[len("_nav_"):]
            st.sidebar.markdown(f"###### {t(f'nav.section.{sec_id}', header)}")
        st.sidebar.radio(
            header or "Navigation",
            [key for _, key in items],
            key=skey,
            index=None,
            format_func=_fmt,
            label_visibility="collapsed",
            on_change=_on_nav_select,
            args=(skey, all_skeys),
        )

    page_key = st.session_state.get('_nav_page', 'home')
    return 'upgrade' if _is_locked(page_key) else page_key


def show_navigation_menu(role: str = 'artist'):
    """Back-compat wrapper: resolve then render in one call."""
    page, rendered, all_skeys = resolve_nav_page(role)
    return render_navigation(role, rendered, all_skeys)

def show_live_activity_sidebar():
    """Live Activity counters in the sidebar — visible on every page."""
    try:
        from src.dashboard.utils import project_db
        from src.dashboard.utils.live_pulse import get_live_pulse
        with project_db() as db:
            live, registered = get_live_pulse(db, ttl_minutes=5)
    except Exception:
        return  # Silently skip if DB unavailable — keeps sidebar usable
    # Un en-tête `###` et deux `st.metric` — le gabarit d'un KPI qu'on vient
    # consulter. Or ce compteur ne demande aucune action et ne change aucune
    # décision : il occupait le haut de la barre latérale, au-dessus de la
    # navigation, pour une information d'ambiance. Une ligne de caption, au-dessus
    # du logo. Le poids visuel suit ce que la chose change pour l'artiste.
    st.sidebar.caption(t("app.live_line", "🟢 {live} en ligne · 👥 {total} artistes")
                       .format(live=f"{live:,}", total=f"{registered:,}"))


# The DAGs the collection button fires, in the order an artist reads them.
COLLECTION_DAGS = [
    ("spotify_api_daily", "Spotify"), ("youtube_daily", "YouTube"),
    ("soundcloud_daily", "SoundCloud"), ("instagram_daily", "Instagram"),
    ("meta_ads_api_daily", "Meta Ads"),
]


def show_data_collection_panel():
    """Sidebar button: collect MY data now.

    Every trigger carries `conf={'artist_id': …}`. Without it the API collectors
    ran fleet-wide and the CSV watchers, which default to `artist_id = 1`, parsed
    the shared drop directory straight into the ADMIN's tenant — while the
    verification e-mail tells every new artist to press this very button.
    """
    from src.dashboard.auth import get_artist_id, is_admin

    artist_id = get_artist_id()
    if artist_id is None and not is_admin():
        # Rule #7: a non-admin without a resolved tenant triggers nothing.
        return
    from src.dashboard.utils.collection_progress import (
        remember_runs, remember_not_launched, render_progress)

    if st.sidebar.button(t("app.run_all_collections", "🚀 Lancer TOUTES les collectes"),
                         type="primary"):
        # La règle de déclenchement vit dans `utils.collection_trigger` — l'étape 4 de
        # l'accueil en avait besoin, et une deuxième copie de « conf={'artist_id': …} »
        # est exactement ce qui a produit la fuite de locataire.
        from src.dashboard.utils.collection_trigger import trigger_all_collections

        # Le panneau ne rend plus RIEN ligne à ligne pendant le déclenchement : sept
        # lignes qui disparaissent, et qui ne parlaient que du déclenchement — « lancé »
        # ne veut pas dire « des données sont arrivées ». Tout ce qui compte descend
        # dans « Collecte en cours », qui survit aux reruns.
        with st.sidebar.status(t("app.syncing", "Synchronisation..."), expanded=False):
            launched, not_launched = trigger_all_collections(
                artist_id, airflow_trigger, COLLECTION_DAGS)
        remember_runs(launched)
        remember_not_launched(not_launched)

    # Reported on every rerun, not only right after the click.
    try:
        from src.dashboard.utils.airflow_monitor import AirflowMonitor
        render_progress(AirflowMonitor(), dict(COLLECTION_DAGS))
    except Exception:
        pass  # progress is informational — never block the sidebar on it

    st.sidebar.markdown("---")

def _check_db_health():
    """Affiche une bannière rouge si PostgreSQL est inaccessible.

    The reachability ping opens its own connection, so it is throttled to once per ~30s
    (cached in session_state) rather than on every rerun — the page render that follows
    surfaces a real outage anyway. Removes one connect+close per rerun per session.
    """
    import time
    cached = st.session_state.get('_db_health_check')
    if cached and time.time() - cached[0] < 30:
        ok = cached[1]
    else:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        ok = db is not None
        if db is not None:
            db.close()
        st.session_state['_db_health_check'] = (time.time(), ok)
    if not ok:
        st.error(t(
            "app.db_health_error",
            "❌ **Base de données PostgreSQL inaccessible.** "
            "Vérifiez que Docker est lancé : `docker-compose up -d`"
        ))
    return ok


def _show_cookie_notice():
    """Cookie notice (RGPD Art. 13) — rendered on the login screen only.

    Il était rendu sur TOUTES les pages jusqu'à ce que l'artiste le referme : un
    encadré `st.info` pleine largeur, en haut du contenu, à côté d'un bouton OK.
    Deux défauts dans le même bloc :

    * il informait APRÈS la connexion, donc après que le cookie a été posé — Art. 13
      demande l'inverse ;
    * il n'appelle aucune action (un cookie de session strictement nécessaire ne se
      refuse pas) et occupait pourtant le gabarit d'un message qui en demande une.

    Une caption sur l'écran de connexion informe au bon moment, sans bouton à
    cliquer et sans état de session à retenir.
    """
    st.caption(t(
        "app.cookie_notice",
        "🍪 Cette plateforme utilise un unique cookie de session (`music_dashboard`) "
        "strictement nécessaire à l'authentification. Aucun tracking, aucun cookie "
        "tiers. [Politique de confidentialité](?page=privacy)"
    ))


def _render_page(page):
    """Dispatch a page key to its view's show(). Wrapped by main()'s error handler
    (C1) — a view crash is caught, alerted, and shown as a friendly message instead
    of Streamlit's raw red traceback. Streamlit st.stop()/st.rerun() signals pass
    through (re-raised in main)."""
    # Free the transient export blobs (a generated PDF/XLSX/ZIP can be several MB held
    # in session_state) as soon as the user leaves the export page — they are only
    # needed to back the on-page download button. Without this they linger in RAM for
    # the whole session, multiplied per concurrent VPS session.
    if page not in ("export_pdf", "export_csv"):
        for _blob_key in ("_export_pdf_bytes", "_export_pdf_autodl",
                          "_export_csv_bytes"):
            st.session_state.pop(_blob_key, None)

    if page == "home":
        from views.home import show; show()

    elif page == "onboarding":
        # L'assistant n'était joignable QUE par `?page=onboarding`, produit uniquement
        # par l'écran post-inscription et l'e-mail de vérification. Mail fermé, onglet
        # fermé : il n'existait plus pour l'artiste, alors que c'est lui — et non
        # `process_guide` — qui porte la sélection par plateforme et la matrice.
        from views.onboarding import show; show()

    # Routing
    elif page == "trigger_algo": from views.trigger_algo import show; show()
    elif page == "meta_ads_overview": from views.meta_ads_overview import show; show()
    elif page == "meta_x_spotify": from views.meta_x_spotify import show; show()
    elif page == "spotify_s4a_combined": from views.spotify_s4a_combined import show; show()
    elif page == "hypeddit": from views.hypeddit import show; show()
    elif page == "apple_music": from views.apple_music import show; show()
    elif page == "youtube": from views.youtube import show; show()
    elif page == "soundcloud": from views.soundcloud import show; show()
    elif page == "instagram": from views.instagram import show; show()
    elif page == "data_wrapped": from views.data_wrapped import show; show()
    elif page == "imusician": from views.imusician import show; show()
    elif page == "credentials": from views.credentials import show; show()
    elif page == "process_guide": from views.process_guide import show; show()
    elif page == "platform_status": from views.platform_status import show; show()
    elif page == "onboarding_health": from views.onboarding_health import show; show()
    elif page == "upload_csv":
        # La page a fusionné dans Credentials le 2026-09-04, mais la ROUTE survit :
        # six pointeurs la visent — les boutons d'étape de `setup_completion`, la
        # destination de S4A et Apple Music (`platform_destination`), la colonne
        # « prochaine étape » de la matrice, et les signets. Supprimer la route les
        # transformerait en culs-de-sac, ce que ce dépôt a déjà payé.
        from views.credentials import show; show()
    elif page == "saisie_s4a": from views.saisie_s4a import show; show()
    elif page == "export_pdf": from views.export_pdf import show; show()
    elif page == "export_csv": from views.export_csv import show; show()
    elif page == "airflow_kpi": from views.airflow_kpi import show; show()
    elif page == "db_health": from views.db_health import show; show()
    elif page == "etl_logs": from views.etl_logs import show; show()
    elif page == "ml_performance": from views.ml_performance import show; show()
    elif page == "useful_links": from views.useful_links import show; show()
    elif page == "billing": from views.billing import show; show()
    elif page == "revenue_forecast": from views.revenue_forecast import show; show()
    elif page == "sacem": from views.sacem import show; show()
    elif page == "meta_mapping": from views.meta_mapping import show; show()
    elif page == "admin": from views.admin import show; show()
    elif page == "account": from views.account import show; show()
    elif page == "meta_creatives": from views.meta_creatives import show; show()
    elif page == "meta_breakdowns": from views.meta_breakdowns import show; show()
    elif page == "meta_cpr_optimizer": from views.meta_cpr_optimizer import show; show()
    elif page == "referral": from views.referral import show; show()
    elif page == "referral_kpi": from views.referral_admin import show; show()
    elif page == "promo_admin": from views.promo_admin import show; show()
    elif page == "upgrade": from views.upgrade import show; show()
    elif page == "perf_monitor": from views.perf_monitor import show; show()
    elif page == "usage_analytics": from views.usage_analytics import show; show()
    elif page == "alerts": from views.alerts import show; show()


def main():
    """Frontière d'exception TOTALE. Aucune ligne de l'application ne s'exécute dehors.

    Il existait déjà une frontière — autour de `_render_page` seulement, soit **10 des
    90 lignes** de la fonction ci-dessous. Les 80 autres portaient huit appels de vue,
    dont les surfaces **non authentifiées** : la page vie privée, l'onboarding et les
    barres latérales. Mesuré end-to-end dans un navigateur le 2026-08-23 : avec
    `showErrorDetails=full` — la valeur effective en production ce jour-là — une
    exception rendait dans la page la clé API YouTube en clair (elle voyage dans la
    query string, donc dans le message), plus les chemins de fichiers et le code.

    Le réglage `showErrorDetails=none` ferme la fuite, et il était la SEULE ligne de
    défense pour ces 80 lignes. Un réglage unique dont l'absence est le défaut ne suffit
    pas : la frontière couvre désormais tout, et le réglage devient la seconde ligne.

    Les signaux de contrôle de Streamlit (`st.stop()`, `st.rerun()`) doivent traverser
    intacts, sans quoi toute navigation casse — c'est le seul cas où l'on re-lève.
    """
    from src.dashboard.utils.error_alert import is_control_flow, notify_app_error

    try:
        _main_body()
    except Exception as _exc:                    # noqa: BLE001 — frontière applicative
        if is_control_flow(_exc):
            raise
        notify_app_error(st.session_state.get("_current_page", "?"), _exc)
        st.error(t("app.fatal_error",
                   "❌ Une erreur est survenue. L'administrateur a été notifié ; "
                   "réessayez dans un instant."))


def _main_body():
    # Public routes — accessible without authentication
    _page_param = st.query_params.get("page")

    if _page_param == "register":
        from views.register import show as show_register
        show_register()
        st.stop()

    if _page_param == "privacy":
        from views.privacy import show as show_privacy
        show_privacy()
        st.stop()

    if _page_param == "verify":
        _token = st.query_params.get("token", "")
        _verify_email(_token)
        st.stop()

    if _page_param == "unsubscribe":
        _unsubscribe(st.query_params.get("uid", ""),
                     st.query_params.get("t", ""),
                     st.query_params.get("scope", "marketing"))
        st.stop()

    # RGPD Art. 13 : informer AVANT de poser le cookie, donc sur l'écran de
    # connexion — et là seulement. Il s'affichait sur toutes les pages jusqu'à ce
    # qu'on le referme, c'est-à-dire au moment où le cookie est déjà posé : à la
    # fois plus tard que nécessaire et partout où il ne sert plus.
    if not st.session_state.get('authenticated'):
        _show_cookie_notice()
    if not require_login():
        st.stop()

    # `?page=onboarding` N'A PLUS de route anticipée, et c'était la cause racine.
    #
    # Elle datait du temps où l'assistant n'était joignable QUE par ce lien (e-mail de
    # vérification, écran post-inscription) : elle le rendait seul, puis `st.stop()`.
    # Depuis qu'il est une entrée de menu, deux choses se combinent :
    #   1. `_render_page` route déjà `onboarding` — la route anticipée est redondante ;
    #   2. le miroir d'URL écrit `?page=<page>` à CHAQUE rendu.
    # Donc dès le premier affichage de l'assistant, l'URL portait `?page=onboarding`, et
    # tout rerun suivant repassait par la route anticipée : plus de barre latérale, plus
    # de menu, plus d'étapes, et un clic sur un bouton de la barre latérale qui ne
    # correspondait à aucun widget instancié. « Impossible de revenir aux différentes
    # étapes de config » se lit là. Vérifié au navigateur le 2026-09-04.
    #
    # Le paramètre reste honoré, plus bas, par le même chemin que toutes les autres
    # pages — l'assistant s'affiche donc DANS l'application, pas à sa place.

    # ── La page active vit dans l'URL ─────────────────────────────────────
    # Elle n'y vivait pas : `?page=` était lu une fois puis SUPPRIMÉ, et la page
    # n'existait plus que dans `st.session_state['_nav_page']`. Toute perte de
    # session — rechargement, reconnexion du WebSocket, onglet restauré — renvoyait
    # donc à l'accueil, alors que la langue, elle, survivait (URL + base). C'est
    # l'asymétrie qu'un artiste a signalée en changeant de langue depuis la page
    # Credentials : le seul état de navigation sans support durable était la page.
    #
    # `_page_mirrored` est ce qui rend le miroir sûr. Sans lui, « le paramètre diffère
    # de la page active » désignerait AUSSI le rerun qui suit un clic dans le menu —
    # l'URL y porte encore l'ancienne page — et le paramètre écraserait le clic.
    # En mémorisant ce que le miroir a écrit, on distingue « c'est nous » (à ignorer)
    # de « quelqu'un a ouvert un lien » (à honorer).
    # La mise en route PASSE DEVANT le paramètre d'URL, et c'est le correctif du
    # 2026-09-04 au soir : « pourquoi dès que je m'inscris après reset et que j'ai le
    # mail, ça ne nous emmène pas direct sur les steps de configuration ? »
    #
    # Reproduit au navigateur : l'artiste entre dans l'app, le miroir écrit
    # `?page=home`, il se déconnecte — l'URL de l'écran de connexion porte encore
    # `page=home`. Il se reconnecte : `session_state.clear()` a effacé
    # `_page_mirrored`, la condition ci-dessous passe, `_nav_page` vaut `home`, et
    # `resolve_nav_page` n'a plus rien à décider. Il atterrit dans l'application avec
    # une configuration à 0/4, sans jamais voir les étapes.
    #
    # Deux mécanismes justes qui se contredisaient : le miroir existe pour qu'un
    # rechargement retrouve sa page, l'atterrissage pour qu'un compte non configuré
    # voie sa mise en route. Le second gagne — une page retrouvée n'a de valeur que
    # pour quelqu'un qui sait déjà où il va.
    #
    # `arm_first_run_once` est donc appelée ICI, avant le bloc, et non plus seulement
    # dans `resolve_nav_page`. Elle est idempotente : le deuxième appel ne fait rien.
    arm_first_run_once(st.session_state.get('role', 'artist'))

    if _page_param:
        _nav_keys = {key for _, _, items in _NAV_SECTIONS for _, key in items}
        # Une première arrivée va sur son assistant, sauf si le paramètre vient d'un
        # LIEN qu'on a nous-mêmes envoyé — c'est-à-dire `?page=onboarding`, du mot de
        # bienvenue. Tout le reste est un vestige : l'onglet d'hier, une URL copiée.
        #
        # Le test valait `not in _SETUP_PAGES`, ce qui exemptait Credentials, l'import
        # CSV et l'état des plateformes. Aucun lien n'y envoie au premier jour ; seule
        # une session précédente le fait.
        # « C'est NOUS qui avons écrit ce paramètre. » Le miroir d'URL le pose à chaque
        # navigation interne ; un vestige de session précédente ne l'a pas, parce que
        # la déconnexion vide `session_state`.
        #
        # Ce test n'était consulté que dans la première branche. Conséquence, signalée
        # le 2026-09-04 quelques minutes après le correctif d'atterrissage : « dès
        # qu'on clique sur *Ajouter mes chiffres S4A & Apple*, ça nous ramène à la
        # mise en route ». Le clic posait `_nav_page`, le miroir écrivait
        # `?page=upload_csv`, et au rerun suivant l'atterrissage voyait un paramètre
        # hors `_LANDING_LINKS` et le jetait — sans regarder qu'il venait de nous.
        #
        # La question de l'atterrissage n'est pas « cette page est-elle un lien ? »
        # mais « ce paramètre vient-il d'ailleurs ? ». Un artiste qui NAVIGUE dans son
        # installation navigue ; seul un onglet resté ouvert détourne.
        _own_mirror = _page_param == st.session_state.get('_page_mirrored')
        _setup_landing = (bool(st.session_state.get(FIRST_RUN_FOCUS))
                          and not _own_mirror
                          and _page_param not in _LANDING_LINKS)
        if (_page_param in _nav_keys and not _setup_landing and not _own_mirror):
            st.session_state['_nav_page'] = _page_param
        elif _setup_landing:
            # Sans cette ligne, `resolve_nav_page` garderait la page de la session
            # PRÉCÉDENTE (`_nav_page` survit-il ? non — mais l'URL, elle, revient à
            # chaque rendu) et le paramètre reprendrait la main au rerun suivant.
            st.session_state.pop('_nav_page', None)

    _check_db_health()

    real_role = st.session_state.get('role', 'artist')
    # Brand logo at the very top of the sidebar (just above Live Activity).
    from src.dashboard.utils import logo_html
    # La barre latérale est NUE pendant la mise en route. Demandé le 2026-09-05 :
    # « retire 🎤 Artiste — …, Votre plan : 💎 Premium, Étapes, 🟢 1 en ligne · 👥 5
    # artistes, et la phrase sur le menu complet → le + simple possible ».
    #
    # Chacun de ces éléments répond à une question qu'on ne se pose pas encore : qui
    # suis-je (il vient de se connecter), quel est mon plan (il n'a rien à arbitrer),
    # où en suis-je (deux étapes dont la seconde est un bilan), combien sommes-nous
    # (une statistique de flotte). Ils ont chacun leur place — plus tard, dans
    # l'application.
    #
    # Ce qui RESTE : le logo, et « Se déconnecter ». Un écran dont on ne peut pas
    # sortir n'est pas une aide.
    # `show_live_activity_sidebar()` est descendu APRÈS la résolution de la page :
    # la décision « barre nue ? » dépend de la page, et elle était appelée avant que
    # la page soit connue.
    _sb_logo = logo_html(variant="adaptive", max_width=220)
    if _sb_logo:
        st.sidebar.markdown(_sb_logo, unsafe_allow_html=True)
    # Admin "Voir comme" QA toggle — must run before the nav so the impersonated plan
    # is set in session_state when get_artist_plan() reads it. An admin previewing
    # free/premium is treated as an 'artist' for role-gating (admin-only pages hidden).
    if real_role == 'admin':
        show_view_as_selector()
    _view_as = st.session_state.get('_view_as')
    role = 'artist' if (real_role == 'admin' and _view_as in ('free', 'premium')) else real_role

    # ── L'ordre de la barre latérale ─────────────────────────────────────────
    # Qui je suis → où j'en suis → où je vais → ce que je lance. Il était : ce que je
    # lance → où je vais → … → qui je suis, tout en bas, sous le menu ; et la liste des
    # étapes de l'assistant arrivait APRÈS tout ça, écrite par la vue elle-même.
    # C'est pour cela que la page est résolue AVANT d'être rendue : rien ne peut se
    # placer au-dessus de la navigation tant que c'est la navigation qui calcule la page.
    page, _rendered, _all_skeys = resolve_nav_page(role)

    # UN SEUL sélecteur de langue à la fois, et c'est un correctif de plantage.
    #
    # L'assistant porte le sien (bloc 0). Le radio de la barre latérale, lui, réimpose
    # sa propre valeur à chaque rendu : pour qu'un choix fait sur la page survive, la
    # page écrivait la clé `_lang_sel`… depuis la phase CONTENU, donc APRÈS que le
    # widget existe. Streamlit l'interdit, et la page mourait sur
    # `❌ Une erreur est survenue` — en anglais, sans moyen de revenir au français.
    # Trouvé en une requête dans `app_error_log` (migration 083), qui existait depuis
    # trois heures : `StreamlitAPIException` dans `_language_buttons`.
    #
    # Deux propriétaires pour un même réglage, c'est le défaut. Sur l'assistant, la
    # page est propriétaire ; ailleurs, la barre. Aucune écriture croisée.
    # UNE seule décision, prise une fois : sommes-nous sur l'écran de mise en route
    # d'un compte qui n'a pas fini ? Elle était éparpillée en trois conditions
    # (`page != 'onboarding'`, `page == 'onboarding'`, `_focus`) qui disaient presque
    # la même chose et divergeaient — un artiste ADMIN voyait les étapes sans le mode
    # première connexion, par exemple.
    _bare = bool(st.session_state.get(FIRST_RUN_FOCUS)) and page == 'onboarding'

    from src.dashboard.utils.i18n import language_selector
    if not _bare:
        # Pendant la mise en route, la langue se choisit SUR la page (bloc 0) : deux
        # sélecteurs pour un réglage se réécrivent l'un l'autre.
        language_selector()
        show_live_activity_sidebar()
        show_user_sidebar(get_artist_plan())

    # Première connexion : la mise en route, et rien d'autre.
    #
    # Le menu complet et le bouton de collecte à côté d'un compte qui n'a encore aucune
    # identité déclarée offrent 40 destinations dont aucune n'a de données à montrer, et
    # une action qui ne peut rien collecter. Demandé le 2026-09-04 après avoir rejoué
    # l'onboarding depuis zéro. Ce n'est PAS une porte : la sortie est le gros bouton en
    # bas de la page, et décocher la case rend le menu sur-le-champ.
    # La phrase « Le menu complet apparaîtra dès que tu entres dans l'application »
    # est partie avec le reste : elle expliquait une absence à quelqu'un qui ne l'a
    # pas remarquée, et la sortie est le gros bouton au milieu de la page.
    if not _bare:
        page = render_navigation(role, _rendered, _all_skeys)
        show_data_collection_panel()

    # La sortie, en dernier, dans les DEUX branches — y compris en première connexion,
    # où le menu n'est pas rendu. Un écran dont on ne peut pas sortir n'est pas une
    # aide (même raison que le gros bouton de l'assistant).
    render_logout_footer()

    # Le miroir : l'URL nomme la page en cours, donc un rechargement la retrouve.
    # Écriture gardée — réécrire la même valeur relancerait le script en boucle.
    try:
        if st.query_params.get("page") != page:
            st.query_params["page"] = page
        st.session_state['_page_mirrored'] = page
    except Exception:      # noqa: BLE001 — hors contexte Streamlit (tests headless)
        pass

    # First-party usage tracking — deduped per session (no inflation on rerun).
    from src.dashboard.utils.usage_tracker import track_page_view
    track_page_view(page)

    _t0 = time.perf_counter()

    try:
        _render_page(page)
    except Exception as _exc:                       # noqa: BLE001 — central view guard
        from src.dashboard.utils.error_alert import is_control_flow, notify_app_error
        if is_control_flow(_exc):
            raise                                   # st.stop()/st.rerun() must propagate
        notify_app_error(page, _exc)
        st.error(t("app.view_error",
                   "❌ Une erreur est survenue sur cette page. Réessayez ; "
                   "l'administrateur a été notifié si le problème persiste."))

    # Record render time (rolling 100-entry log, stored in session state)
    _render_ms = int((time.perf_counter() - _t0) * 1000)
    log = st.session_state.setdefault('_perf_log', [])
    log.append({'page': page, 'ms': _render_ms, 'ts': datetime.now().strftime('%H:%M:%S')})
    if len(log) > 100:
        st.session_state['_perf_log'] = log[-100:]

if __name__ == "__main__":
    main()
