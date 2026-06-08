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
from dotenv import load_dotenv
import os

# ✅ IMPORTANT : Ajouter le chemin AVANT les imports src.*
# resolve() → chemin absolu garanti, insert(0) → priorité maximale
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ✅ Charger .env.local si disponible
env_file = '.env.local' if os.path.exists('.env.local') else '.env'
load_dotenv(env_file)

from src.utils.config_loader import config_loader
from src.utils.airflow_trigger import AirflowTrigger
from src.dashboard.auth import require_login, show_user_sidebar, get_artist_plan
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
airflow_trigger = AirflowTrigger(
    base_url=os.getenv('AIRFLOW_BASE_URL', airflow_config.get('base_url', 'http://localhost:8080')),
    username=os.getenv('AIRFLOW_USERNAME', airflow_config.get('username', 'admin')),
    password=_airflow_pass,
)

def _verify_email(token: str) -> None:
    """Handle the email verification link (?page=verify&token=xxx)."""
    st.title("🎵 Email verification")
    if not token:
        st.error("Invalid verification link.")
        return
    from src.dashboard.utils import get_db_connection
    db = get_db_connection()
    if db is None:
        st.error("Database unreachable.")
        return
    try:
        rows = db.fetch_query(
            "SELECT id, username, email_verified, verification_token_created_at "
            "FROM saas_users "
            "WHERE verification_token = %s LIMIT 1",
            (token,)
        )
        if not rows:
            st.error("This verification link is invalid or has already been used.")
            return
        uid, username, already_verified, token_created_at = rows[0]
        if already_verified:
            st.info(f"Account **{username}** is already verified. [Sign in](/)")
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
                st.error(
                    "This verification link has expired (48 hours). "
                    "Please register again or use the resend option on the sign-in page."
                )
                return
        db.execute_query(
            "UPDATE saas_users SET email_verified = TRUE, verification_token = NULL, "
            "verification_token_created_at = NULL WHERE id = %s",
            (uid,)
        )
        st.success(
            f"✅ Email verified! Welcome, **{username}**. "
            "You can now [sign in](/)."
        )
    finally:
        db.close()


# Sidebar layout: ordered sections, each (stable_id, header_label, [(item_label, page_key), ...]).
# Order = user journey. Empty header = no visual separator (top entry).
_NAV_SECTIONS = [
    ("start",     "",                       [("🏠 Accueil", "home")]),
    ("data",      "📁 Données",             [("📋 Guide de démarrage", "process_guide"),
                                             ("🔑 Credentials API", "credentials"),
                                             ("📂 Import CSV", "upload_csv"),
                                             ("📝 Saisie S4A (playlist & Discovery)", "saisie_s4a"),
                                             ("🔗 Mapping Spotify × Meta Ads (nom de campagne)", "meta_mapping"),
                                             ("🗄️ Santé des données", "db_health")]),
    ("analytics", "📊 Analytics plateformes", [("🎵 Spotify & S4A", "spotify_s4a_combined"),
                                             ("🎵 META x Spotify", "meta_x_spotify"),
                                             ("🎎 Apple Music", "apple_music"),
                                             ("🎬 YouTube", "youtube"),
                                             ("☁️ SoundCloud", "soundcloud"),
                                             ("📸 Instagram", "instagram"),
                                             ("📱 Hypeddit", "hypeddit")]),
    ("advanced",  "🔮 Prédiction algos Spotify", [("🚀 Road to Algo (ML)", "trigger_algo")]),
    ("ads",       "📣 Publicité Meta Ads",  [("📱 Vue d'ensemble", "meta_ads_overview"),
                                             ("🎨 Créatives", "meta_creatives"),
                                             ("🌍 Breakdowns Meta", "meta_breakdowns"),
                                             ("📊 CPR Optimizer", "meta_cpr_optimizer")]),
    ("revenue",   "💶 Revenus",             [("💰 Distributeur", "imusician"),
                                             ("📈 Prévisions revenus", "revenue_forecast")]),
    ("reports",   "📑 Rapports & exports",  [("🎁 Data Wrapped", "data_wrapped"),
                                             ("📄 Export PDF", "export_pdf"),
                                             ("⬇️ Export CSV", "export_csv")]),
    ("account",   "👤 Compte",              [("👤 Mon compte", "account"),
                                             ("💳 Billing", "billing"),
                                             ("🎁 Parrainage", "referral")]),
    ("admin",     "🛠️ Admin / Ops",        [("⚡ Perf. Dashboard", "perf_monitor"),
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
               'etl_logs', 'referral_kpi', 'promo_admin', 'perf_monitor'}


def _on_nav_select(skey: str, all_skeys: list):
    """Radio callback: keep a single active page across all section radios."""
    val = st.session_state.get(skey)
    if val is None:
        return  # deselection echo — ignore
    st.session_state['_nav_page'] = val
    for other in all_skeys:
        if other != skey:
            st.session_state[other] = None


def show_navigation_menu(role: str = 'artist'):
    st.sidebar.title("🎵 Navigation")

    # Plan-based gating: locked pages shown with 🔒 and routed to upgrade view
    plan = get_artist_plan()
    accessible = PLAN_FEATURES.get(plan, set())
    is_all = '*' in accessible  # premium: unrestricted

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
        st.session_state['_nav_page'] = 'home'
        for skey in all_skeys:
            st.session_state[skey] = None
        st.session_state['_nav_start'] = 'home'  # home lives in the first section

    label_by_key = {key: lbl for _, _, items in rendered for lbl, key in items}

    def _fmt(key: str) -> str:
        return f"🔒 {label_by_key[key]}" if _is_locked(key) else label_by_key[key]

    for skey, header, items in rendered:
        if header:
            st.sidebar.markdown(f"###### {header}")
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
    st.sidebar.markdown("### 🟢 Live Activity")
    c1, c2 = st.sidebar.columns(2)
    c1.metric("🟢 Actifs", f"{live:,}", help="Artists active within the last 5 minutes")
    c2.metric("👥 Total", f"{registered:,}", help="Total active artist accounts")
    st.sidebar.markdown("---")


def show_data_collection_panel():
    if st.sidebar.button("🚀 Lancer TOUTES les collectes", type="primary"):
        with st.sidebar.status("Synchronisation...", expanded=True):
            dags = [("spotify_api_daily", "Spotify"), ("youtube_daily", "YouTube"),
                    ("soundcloud_daily", "SoundCloud"), ("instagram_daily", "Instagram"),
                    ("s4a_csv_watcher", "CSV S4A"), ("apple_music_csv_watcher", "CSV Apple"),
                    ("meta_ads_api_daily", "Meta Ads")]
            for dag_id, label in dags:
                try:
                    if airflow_trigger.trigger_dag(dag_id).get('success'): st.write(f"✅ {label}")
                    else: st.error(f"❌ {label}")
                except: st.error(f"❌ {label}")
            st.sidebar.success("Lancé !")
    st.sidebar.markdown("---")

def _check_db_health():
    """Affiche une bannière rouge si PostgreSQL est inaccessible."""
    from src.dashboard.utils import get_db_connection
    db = get_db_connection()
    if db is None:
        st.error(
            "❌ **Base de données PostgreSQL inaccessible.** "
            "Vérifiez que Docker est lancé : `docker-compose up -d`"
        )
        return False
    db.close()
    return True


def _show_cookie_notice():
    """Display a one-time cookie notice per session (RGPD Art. 13)."""
    if st.session_state.get('_cookie_notice_dismissed'):
        return
    with st.container():
        cols = st.columns([8, 1])
        cols[0].info(
            "🍪 This platform uses a single session cookie (`music_dashboard`) "
            "strictly necessary for authentication. No tracking, no third-party cookies. "
            "[Privacy Policy](?page=privacy)"
        )
        if cols[1].button("OK", key="_dismiss_cookie"):
            st.session_state['_cookie_notice_dismissed'] = True
            st.rerun()


def main():
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

    if not require_login():
        st.stop()

    if _page_param == "onboarding":
        from views.onboarding import show as show_onboarding
        show_onboarding()
        st.stop()

    _check_db_health()
    _show_cookie_notice()

    role = st.session_state.get('role', 'artist')
    show_live_activity_sidebar()
    show_data_collection_panel()
    page = show_navigation_menu(role)
    show_user_sidebar()

    _t0 = time.perf_counter()

    if page == "home":
        from views.home import show; show()

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
    elif page == "alerts": from views.alerts import show; show()

    # Record render time (rolling 100-entry log, stored in session state)
    _render_ms = int((time.perf_counter() - _t0) * 1000)
    log = st.session_state.setdefault('_perf_log', [])
    log.append({'page': page, 'ms': _render_ms, 'ts': datetime.now().strftime('%H:%M:%S')})
    if len(log) > 100:
        st.session_state['_perf_log'] = log[-100:]

if __name__ == "__main__":
    main()
