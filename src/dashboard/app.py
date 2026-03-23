"""Application Streamlit principale avec déclenchement des DAGs."""
import streamlit as st
from pathlib import Path
import sys
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
from src.dashboard.auth import require_login, show_user_sidebar

st.set_page_config(page_title="Music Dashboard", page_icon="🎵", layout="wide")

config = config_loader.load()
airflow_config = config.get('airflow', {})
airflow_trigger = AirflowTrigger(
    base_url=airflow_config.get('base_url', 'http://localhost:8080'),
    username=airflow_config.get('username', 'admin'),
    password=airflow_config.get('password', 'admin')
)

def show_navigation_menu(role: str = 'artist'):
    st.sidebar.title("🎵 Navigation")
    pages_all = {
        "🏠 Accueil": "home",
        "🚀 Road to Algo (ML)": "trigger_algo",
        "📱 Meta Ads - Vue d'ensemble": "meta_ads_overview",
        "🎵 META x Spotify": "meta_x_spotify",
        "🎵 Spotify & S4A": "spotify_s4a_combined",
        "📱 Hypeddit": "hypeddit",
        "☁️ SoundCloud": "soundcloud",
        "📸 Instagram": "instagram",
        "🎎 Apple Music": "apple_music",
        "🎬 YouTube": "youtube",
        "💰 iMusician": "imusician",
        "🔑 Credentials API": "credentials",
        "📂 Import CSV": "upload_csv",
        "📄 Export PDF": "export_pdf",
        "⬇️ Export CSV": "export_csv",
        "🏗️ Monitoring ETL": "airflow_kpi",
        "🤖 Perf. Modèles ML": "ml_performance",
        "🔧 Liens & Outils": "useful_links",
        "⚙️ Admin": "admin",
    }
    # Pages réservées admin (cachées pour le rôle 'artist')
    _admin_only = {'airflow_kpi', 'admin', 'ml_performance', 'useful_links'}
    pages = pages_all if role == 'admin' else {k: v for k, v in pages_all.items() if v not in _admin_only}
    return pages[st.sidebar.radio("Aller à ", list(pages.keys()), label_visibility="collapsed")]

def show_data_collection_panel():
    st.sidebar.markdown("---")
    if st.sidebar.button("🚀 Lancer TOUTES les collectes", type="primary"):
        with st.sidebar.status("Synchronisation...", expanded=True):
            dags = [("spotify_api_daily", "Spotify"), ("youtube_daily", "YouTube"),
                    ("soundcloud_daily", "SoundCloud"), ("instagram_daily", "Instagram"),
                    ("s4a_csv_watcher", "CSV S4A"), ("apple_music_csv_watcher", "CSV Apple"),
                    ("meta_csv_watcher_config", "Meta Config"), ("meta_insights_watcher", "Meta Stats")]
            for dag_id, label in dags:
                try:
                    if airflow_trigger.trigger_dag(dag_id).get('success'): st.write(f"✅ {label}")
                    else: st.error(f"❌ {label}")
                except: st.error(f"❌ {label}")
            st.sidebar.success("Lancé !")

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


def main():
    if not require_login():
        st.stop()

    _check_db_health()

    role = st.session_state.get('role', 'artist')
    page = show_navigation_menu(role)
    show_user_sidebar()
    show_data_collection_panel()
    
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
    elif page == "imusician": from views.imusician import show; show()
    elif page == "credentials": from views.credentials import show; show()
    elif page == "upload_csv": from views.upload_csv import show; show()
    elif page == "export_pdf": from views.export_pdf import show; show()
    elif page == "export_csv": from views.export_csv import show; show()
    elif page == "airflow_kpi": from views.airflow_kpi import show; show()
    elif page == "ml_performance": from views.ml_performance import show; show()
    elif page == "useful_links": from views.useful_links import show; show()
    elif page == "admin": from views.admin import show; show()

if __name__ == "__main__":
    main()