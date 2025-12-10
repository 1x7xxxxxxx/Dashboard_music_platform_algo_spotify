"""Application Streamlit principale avec déclenchement des DAGs."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

# ✅ IMPORTANT : Ajouter le chemin AVANT les imports src.*
sys.path.append(str(Path(__file__).parent.parent.parent))

# ✅ Charger .env.local si disponible (priorité)
env_file = '.env.local' if os.path.exists('.env.local') else '.env'
load_dotenv(env_file)

# ✅ Imports après sys.path.append
from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader
from src.utils.airflow_trigger import AirflowTrigger

# Configuration de la page
st.set_page_config(
    page_title="Music Platform Dashboard",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialiser AirflowTrigger
config = config_loader.load()
airflow_config = config.get('airflow', {})
airflow_trigger = AirflowTrigger(
    base_url=airflow_config.get('base_url', 'http://localhost:8080'),
    username=airflow_config.get('username', 'admin'),
    password=airflow_config.get('password', 'admin')
)


def get_db():
    """Connexion PostgreSQL."""
    config = config_loader.load()
    db_config = config['database']
    return PostgresHandler(
        host=db_config['host'],
        port=db_config['port'],
        database=db_config['database'],
        user=db_config['user'],
        password=db_config['password']
    )


def show_navigation_menu():
    """Affiche le menu de navigation dans la sidebar."""
    st.sidebar.title("🎵 Navigation")
    
    pages = {
        "🏠 Accueil": "home",
        "📱 Meta Ads - Vue d'ensemble": "meta_ads_overview",
        "🎵 META x Spotify": "meta_x_spotify",
        "🎵 Spotify & S4A": "spotify_s4a_combined",
        "📱 Hypeddit": "hypeddit",
        "☁️ SoundCloud": "soundcloud",  # ✅ AJOUTÉ ICI
        "🎎 Apple Music": "apple_music",
        "🎬 YouTube": "youtube",
    }
    
    # Utiliser st.radio pour la navigation
    selection = st.sidebar.radio("Aller à ", list(pages.keys()), label_visibility="collapsed")
    
    return pages[selection]


def show_data_collection_panel():
    """Affiche le panneau de collecte de données (Bouton Unique + Individuels)."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔄 Synchronisation")
    
    # Bouton Maître
    if st.sidebar.button("🚀 Lancer TOUTES les collectes", type="primary"):
        with st.sidebar.status("Démarrage des pipelines...", expanded=True) as status:
            
            # Liste précise des DAGs actifs à lancer
            dags_to_run = [
                ("spotify_api_daily", "Spotify API"),
                ("youtube_daily", "YouTube Data"),
                ("soundcloud_daily", "SoundCloud Data"), # ✅ AJOUTÉ ICI
                ("s4a_csv_watcher", "CSV Spotify Artists"),
                ("apple_music_csv_watcher", "CSV Apple Music"),
                ("meta_csv_watcher_config", "Meta Ads (Config)"),
                ("meta_insights_watcher", "Meta Ads (Stats)"),
                ("data_quality_check", "Check Qualité")
            ]
            
            success_count = 0
            
            for dag_id, label in dags_to_run:
                st.write(f"⏳ {label}...")
                try:
                    result = airflow_trigger.trigger_dag(dag_id)
                    
                    if result.get('success'):
                        st.write(f"✅ {label}")
                        success_count += 1
                    else:
                        error_msg = result.get('error', 'Erreur inconnue')
                        st.error(f"❌ {label}: {error_msg}")
                        
                except Exception as e:
                    st.error(f"❌ {label}: Erreur appel ({e})")
            
            if success_count == len(dags_to_run):
                status.update(label="✅ Tout est lancé !", state="complete")
                st.sidebar.success("Rafraîchissez dans quelques minutes.")
            else:
                status.update(label="⚠️ Lancement partiel", state="error")
    
    st.sidebar.caption("Cela traitera tous les fichiers CSV présents dans le dossier `data/raw` et lancera les API.")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 🛠️ Collectes Individuelles")
    
    # Layout en colonnes pour les boutons individuels
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        # Spotify API
        if st.button("🎸 Spotify API", help="Artistes & Tracks", key="trigger_spotify"):
            with st.spinner('Lancement...'):
                res = airflow_trigger.trigger_dag('spotify_api_daily')
                if res.get('success'): st.success("✅ Lancé")
                else: st.error("❌ Erreur")
        
        # S4A CSV
        if st.button("🎵 CSV S4A", help="Spotify for Artists", key="trigger_s4a"):
            with st.spinner('Lancement...'):
                res = airflow_trigger.trigger_dag('s4a_csv_watcher')
                if res.get('success'): st.success("✅ Lancé")
                else: st.error("❌ Erreur")
                
        # Meta Ads CSV (Nouveau)
        if st.button("📱 CSV Meta", help="Meta Ads", key="trigger_meta"):
             with st.spinner('Lancement...'):
                # On lance les deux pour Meta
                r1 = airflow_trigger.trigger_dag('meta_csv_watcher_config')
                r2 = airflow_trigger.trigger_dag('meta_insights_watcher')
                if r1.get('success') and r2.get('success'): st.success("✅ Lancé")
                else: st.error("❌ Erreur")

    with col2:
        # Apple Music CSV
        if st.button("🎎 CSV Apple", help="Apple Music", key="trigger_apple"):
            with st.spinner('Lancement...'):
                res = airflow_trigger.trigger_dag('apple_music_csv_watcher')
                if res.get('success'): st.success("✅ Lancé")
                else: st.error("❌ Erreur")
        
        # YouTube
        if st.button("🎬 YouTube", help="Données YouTube", key="trigger_youtube"):
            with st.spinner('Lancement...'):
                res = airflow_trigger.trigger_dag('youtube_daily')
                if res.get('success'): st.success("✅ Lancé")
                else: st.error("❌ Erreur")

        # SoundCloud (Nouveau)
        if st.button("☁️ SoundCloud", help="Données SoundCloud", key="trigger_sc"): # ✅ AJOUTÉ ICI
            with st.spinner('Lancement...'):
                res = airflow_trigger.trigger_dag('soundcloud_daily')
                if res.get('success'): st.success("✅ Lancé")
                else: st.error("❌ Erreur")
        
    # Bouton Qualité (seul en bas)
    if st.sidebar.button("🔍 Vérifier Qualité Données", key="trigger_quality"):
        with st.spinner('Vérification...'):
            res = airflow_trigger.trigger_dag('data_quality_check')
            if res.get('success'): st.success("✅ Vérification lancée")
            else: st.error("❌ Erreur")


def main():
    """Page principale."""
    # 1. Menu de navigation en premier (en haut de la sidebar)
    page = show_navigation_menu()
    
    # 2. Panneau de collecte en dessous
    show_data_collection_panel()
    
    # 3. Charger la page sélectionnée
    if page == "home":
        st.title("🎵 Music Platform Dashboard")
        st.markdown("---")
        
        st.markdown("""
        ## 🎯 Bienvenue sur votre Dashboard Musical !
        
        ### 🔄 Collecte de données
        **Utilisez le panneau de gauche pour lancer les collectes :**
        - 📱 **Meta Ads** : Campagnes publicitaires (CSV)
        - 🎸 **Spotify API** : Artistes, tracks et historique
        - 🎵 **CSV S4A** : Spotify for Artists
        - ☁️ **SoundCloud** : Stats quotidiennes via API
        - 🎎 **CSV Apple** : Apple Music
        - 🎬 **YouTube** : Statistiques de chaîne
        
        ### 📊 Sources de données
        - ✅ Meta Ads (CSV)
        - ✅ Spotify API & S4A (CSV)
        - ✅ SoundCloud API
        - ✅ Apple Music (CSV)
        - ✅ YouTube API
        - ✅ PostgreSQL stockage centralisé
        """)
        
        # Statistiques rapides
        st.markdown("---")
        st.subheader("📊 Aperçu Rapide")
        
        db = get_db()
        
        try:
            col1, col2, col3, col4 = st.columns(4)
            
            # Count Meta Ads
            try:
                meta_count = db.fetch_query("SELECT COUNT(*) FROM meta_campaigns")[0][0]
            except: meta_count = 0
            col1.metric("📱 Campagnes Meta", f"{meta_count:,}")
            
            # Count Spotify Artists
            try:
                artists_count = db.fetch_query("SELECT COUNT(*) FROM artists")[0][0]
            except: artists_count = 0
            col2.metric("👤 Artistes Spotify", f"{artists_count:,}")
            
            # Count SoundCloud
            try:
                sc_count = db.fetch_query("SELECT COUNT(DISTINCT track_id) FROM soundcloud_tracks_daily")[0][0]
            except: sc_count = 0
            col3.metric("☁️ Titres SoundCloud", f"{sc_count:,}") # ✅ AJOUTÉ ICI
            
            # Count YouTube
            try:
                youtube_count = db.fetch_query("SELECT COUNT(*) FROM youtube_videos")[0][0]
            except: youtube_count = 0
            col4.metric("🎬 Vidéos YouTube", f"{youtube_count:,}")
            
            # Deuxième ligne de KPIs
            st.markdown("")
            c1, c2, c3 = st.columns(3)
            
            # Count S4A
            try:
                s4a_count = db.fetch_query("SELECT COUNT(*) FROM s4a_song_timeline")[0][0]
            except: s4a_count = 0
            c1.metric("🎵 Timeline S4A", f"{s4a_count:,}")
            
            # Count Apple
            try:
                apple_count = db.fetch_query("SELECT COUNT(*) FROM apple_songs_performance")[0][0]
            except: apple_count = 0
            c2.metric("🎎 Chansons Apple", f"{apple_count:,}")

            # Date
            c3.metric("🕐 Date", datetime.now().strftime("%d/%m/%Y"))
        
        except Exception as e:
            st.error(f"❌ Erreur lors du chargement des statistiques: {e}")
        
        finally:
            db.close()
        
        st.markdown("---")
        
        # Statut Airflow
        st.subheader("🔧 Statut Airflow")
        col1, col2 = st.columns(2)
        with col1:
            st.info("**Interface Airflow:** http://localhost:8080")
        with col2:
            if st.button("🔗 Ouvrir Airflow UI"):
                st.markdown("[Cliquez ici pour ouvrir Airflow](http://localhost:8080)")
    
    elif page == "meta_ads_overview":
        from views.meta_ads_overview import show
        show()
    
    elif page == "meta_x_spotify":
        from views.meta_x_spotify import show
        show()
    
    elif page == "spotify_s4a_combined":
        from views.spotify_s4a_combined import show
        show()
    
    elif page == "hypeddit":
        from views.hypeddit_overview import show
        show()
    
    elif page == "apple_music":
        from views.apple_music import show
        show()

    elif page == "youtube":
        from views.youtube import show
        show()

    elif page == "soundcloud": 
        from views.soundcloud import show
        show()        


if __name__ == "__main__":
    main()