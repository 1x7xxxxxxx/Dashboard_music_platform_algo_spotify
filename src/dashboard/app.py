"""Application Streamlit principale avec déclenchement des DAGs."""
import warnings

# Harmless duplicate-matplotlib warning (Axes3D import) emitted transitively at import
# time — silenced before any view imports matplotlib/altair so it never reaches the UI/logs.
warnings.filterwarnings("ignore", message="Unable to import Axes3D")

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

# Resolve .env from the repository root, NOT from the cwd: the documented launch is
# `cd src/dashboard && streamlit run app.py`, where the cwd-relative test below found
# neither file and load_dotenv() returned False without a word (measured 2026-08-21).
from src.utils.env_files import load_project_env  # noqa: E402

load_project_env()

from src.utils.config_loader import config_loader
from src.utils.airflow_trigger import AirflowTrigger
from src.dashboard.auth import require_login, show_user_sidebar, get_artist_plan
from src.dashboard.utils.i18n import t, get_lang
from src.database.stripe_schema import PLAN_FEATURES, ALWAYS_ACCESSIBLE

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
                      "Le compte **{u}** est déjà vérifié. [Se connecter](/)").format(u=username))
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
        # Un lien en markdown au milieu d'un paragraphe se rate. À cet instant il n'y
        # a qu'une chose à faire, et elle mérite un bouton.
        st.link_button(t("app.verify_login_btn", "→ Me connecter"), "/", type="primary")
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


def _unsubscribe(uid: str, token: str) -> None:
    """Handle the one-click unsubscribe link (?page=unsubscribe&uid=&t=).

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
    ("data",      "📁 Données",             [("🚀 Mise en route (assistant)", "onboarding"),
                                             ("📋 Guide de démarrage", "process_guide"),
                                             ("🔑 Credentials API", "credentials"),
                                             ("📂 Import CSV", "upload_csv"),
                                             ("🔗 Mapping cross-plateforme", "meta_mapping"),
                                             ("🚦 Santé onboarding", "onboarding_health"),
                                             ("🗄️ Santé des données", "db_health")]),
    ("analytics", "📊 Analytics plateformes", [("🎵 Spotify & S4A", "spotify_s4a_combined"),
                                             ("🎵 META x Spotify", "meta_x_spotify"),
                                             ("🎎 Apple Music", "apple_music"),
                                             ("🎬 YouTube", "youtube"),
                                             ("☁️ SoundCloud", "soundcloud"),
                                             ("📸 Instagram", "instagram"),
                                             ("📱 Hypeddit", "hypeddit")]),
    ("advanced",  "🔮 Prédiction algos Spotify", [("📝 Saisie S4A (playlist & Discovery)", "saisie_s4a"),
                                             ("🚀 Road to Algo (ML)", "trigger_algo")]),
    ("ads",       "📣 Publicité Meta Ads",  [("📱 Vue d'ensemble", "meta_ads_overview"),
                                             ("🎨 Créatives", "meta_creatives"),
                                             ("🌍 Breakdowns Meta", "meta_breakdowns"),
                                             ("📊 CPR Optimizer", "meta_cpr_optimizer")]),
    ("revenue",   "💶 Revenus",             [("💰 Distributeur", "imusician"),
                                             ("🎼 SACEM", "sacem"),
                                             ("📈 Prévisions revenus", "revenue_forecast")]),
    ("reports",   "🎁 Rapports & exports",  [("🎁 Data Wrapped", "data_wrapped"),
                                             ("📄 Export PDF", "export_pdf"),
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


def _first_run_landing(role: str) -> str:
    """`onboarding` tant que l'artiste n'a RIEN branché, `home` ensuite.

    Tout le monde atterrissait sur `home` sans condition. Pour un artiste qui vient de
    s'inscrire, `home` est un tableau d'état vide : quatre tuiles à zéro et des cartes de
    fraîcheur qui n'ont rien à rafraîchir. Il ne dit pas quoi faire, et l'assistant qui le
    dirait n'était joignable que depuis l'e-mail de vérification.

    Ne se déclenche qu'à la PREMIÈRE évaluation de la session (`_nav_page` absent), donc
    un artiste qui navigue ensuite vers l'accueil y reste. Et seulement tant que rien
    n'est configuré : dès la première identité déclarée, l'atterrissage redevient `home`,
    ce que demandait la note (« tomber direct sur guide de démarrage … et ensuite sur
    accueil »).

    Toute erreur retombe sur `home` : un aiguillage d'accueil ne doit jamais empêcher
    d'entrer dans l'application.
    """
    if role == 'admin':
        return 'home'
    try:
        from src.dashboard.auth import get_artist_id
        artist_id = get_artist_id()
        if artist_id is None:
            return 'home'
        from src.dashboard.utils import get_db_connection
        from src.utils.artist_readiness import artist_readiness
        db = get_db_connection()
        if db is None:
            return 'home'
        try:
            rows = artist_readiness(db, artist_id)
        finally:
            db.close()
        # `todo` == aucune identité déclarée pour cette plateforme. Tout en `todo`
        # signifie que l'artiste n'a strictement rien branché.
        nothing_yet = bool(rows) and all(r.get("status") == "todo" for r in rows)
        return 'onboarding' if nothing_yet else 'home'
    except Exception:      # noqa: BLE001 — jamais bloquer l'entrée dans l'app
        return 'home'


def show_navigation_menu(role: str = 'artist'):
    st.sidebar.title(t("nav.title", "🎵 Navigation"))

    # Plan-based gating: locked pages shown with 🔒 and routed to upgrade view
    plan = get_artist_plan()
    accessible = PLAN_FEATURES.get(plan, set())
    is_all = '*' in accessible  # premium: unrestricted

    # Artist-facing plan vision: show the current plan + flag that 🔒 items are the
    # Premium upsell (shown indicatively, never hidden). Admins use the toggle instead.
    if role != 'admin':
        if plan == 'premium':
            st.sidebar.caption(t("nav.plan_badge_premium", "Votre plan : **💎 Premium**"))
        else:
            st.sidebar.caption(
                t("nav.plan_badge_free",
                  "Votre plan : **🆓 Free**  ·  🔒 = fonctions **Premium**"))

    def _is_locked(key: str) -> bool:
        return not (is_all or key in ALWAYS_ACCESSIBLE or key in accessible)

    # Filter sections by role; drop empty sections entirely (no orphan header)
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
        for skey in all_skeys:
            st.session_state[skey] = None
        st.session_state['_nav_start'] = landing if landing in visible_keys else 'home'

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
    ("s4a_csv_watcher", "CSV S4A"), ("apple_music_csv_watcher", "CSV Apple"),
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
        from src.utils.safe_error import safe_error

        launched: dict[str, str] = {}
        not_launched: dict[str, str] = {}
        # Le panneau ne rend plus RIEN ligne à ligne pendant le déclenchement.
        # Il affichait « ✅ Spotify » par plateforme puis « Lancé ! », dans une
        # `st.status` qui se referme : sept lignes qui disparaissent, et qui ne
        # parlaient que du déclenchement — pas de la collecte. « Lancé » ne veut pas
        # dire « des données sont arrivées », et c'est bien la deuxième chose que
        # l'artiste allait vérifier. Tout ce qui compte — y compris un déclenchement
        # REFUSÉ — descend maintenant dans « Collecte en cours », qui survit aux
        # reruns et se met à jour tout seul.
        with st.sidebar.status(t("app.syncing", "Synchronisation..."), expanded=False):
            for dag_id, label in COLLECTION_DAGS:
                try:
                    conf = {'artist_id': artist_id} if artist_id is not None else {}
                    result = airflow_trigger.trigger_dag(dag_id, conf=conf)
                    if result.get('success'):
                        # Same reason as views/credentials/_render.py: the cached
                        # "latest run per DAG" is stale the instant a run is launched.
                        from src.dashboard.utils.airflow_monitor import cached_last_run_per_dag
                        cached_last_run_per_dag.clear()
                        # Keep the run id: "Lancé !" was the last thing the artist
                        # ever heard about this collection.
                        if result.get('dag_run_id'):
                            launched[dag_id] = result['dag_run_id']
                    else:
                        # Say WHY: a bare ❌ is what made "toutes les credentials
                        # ont échoué" impossible to act on during a live session.
                        not_launched[dag_id] = str(
                            result.get('error', result.get('message', '')) or '')
                except Exception as e:
                    # `safe_error`, jamais `{e}` : `trigger_dag` parle à l'API REST
                    # d'Airflow avec des identifiants, et ce message est rendu À
                    # L'ARTISTE. `app.py` n'est pas dans la portée du garde
                    # `secret-in-an-exception-message`, donc rien ne l'aurait dit.
                    not_launched[dag_id] = safe_error(e)
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
    elif page == "onboarding_health": from views.onboarding_health import show; show()
    elif page == "upload_csv": from views.upload_csv import show; show()
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
        _unsubscribe(st.query_params.get("uid", ""), st.query_params.get("t", ""))
        st.stop()

    # RGPD Art. 13 : informer AVANT de poser le cookie, donc sur l'écran de
    # connexion — et là seulement. Il s'affichait sur toutes les pages jusqu'à ce
    # qu'on le referme, c'est-à-dire au moment où le cookie est déjà posé : à la
    # fois plus tard que nécessaire et partout où il ne sert plus.
    if not st.session_state.get('authenticated'):
        _show_cookie_notice()
    if not require_login():
        st.stop()

    if _page_param == "onboarding":
        from views.onboarding import show as show_onboarding
        show_onboarding()
        st.stop()

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
    if _page_param:
        _nav_keys = {key for _, _, items in _NAV_SECTIONS for _, key in items}
        if _page_param in _nav_keys and _page_param != st.session_state.get('_page_mirrored'):
            st.session_state['_nav_page'] = _page_param

    _check_db_health()

    real_role = st.session_state.get('role', 'artist')
    # Brand logo at the very top of the sidebar (just above Live Activity).
    from src.dashboard.utils import logo_html
    show_live_activity_sidebar()          # une ligne, juste au-dessus du logo
    _sb_logo = logo_html(variant="adaptive", max_width=220)
    if _sb_logo:
        st.sidebar.markdown(_sb_logo, unsafe_allow_html=True)
    # Language toggle — set before the nav so the whole sidebar renders in the choice.
    from src.dashboard.utils.i18n import language_selector
    language_selector()
    show_data_collection_panel()
    # Admin "Voir comme" QA toggle — must run before the nav so the impersonated plan
    # is set in session_state when get_artist_plan() reads it. An admin previewing
    # free/premium is treated as an 'artist' for role-gating (admin-only pages hidden).
    if real_role == 'admin':
        show_view_as_selector()
    _view_as = st.session_state.get('_view_as')
    role = 'artist' if (real_role == 'admin' and _view_as in ('free', 'premium')) else real_role
    page = show_navigation_menu(role)

    # Le miroir : l'URL nomme la page en cours, donc un rechargement la retrouve.
    # Écriture gardée — réécrire la même valeur relancerait le script en boucle.
    try:
        if st.query_params.get("page") != page:
            st.query_params["page"] = page
        st.session_state['_page_mirrored'] = page
    except Exception:      # noqa: BLE001 — hors contexte Streamlit (tests headless)
        pass

    show_user_sidebar()

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
