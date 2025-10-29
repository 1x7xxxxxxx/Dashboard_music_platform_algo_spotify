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
        "🎎 Apple Music": "apple_music",
        "🎬 YouTube": "youtube",
    }
    
    # Utiliser st.radio pour la navigation
    selection = st.sidebar.radio("Aller à ", list(pages.keys()), label_visibility="collapsed")
    
    return pages[selection]


def show_data_collection_panel():
    """Affiche le panneau de collecte de données."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔄 Collecte de données")
    
    # Bouton pour déclencher toutes les collectes
    if st.sidebar.button("🚀 Lancer toutes les collectes", type="primary"):
        with st.sidebar:
            with st.spinner('Déclenchement des DAGs...'):
                results = airflow_trigger.trigger_all_dags()
                
                # Afficher les résultats
                success_count = sum(1 for r in results if r.get('success'))
                total_count = len(results)
                
                for result in results:
                    if result.get('success'):
                        st.success(f"✅ {result['dag']}")
                    else:
                        st.error(f"❌ {result['dag']}: {result.get('error', 'Erreur inconnue')}")
                
                if success_count == total_count:
                    st.success(f"🎉 Toutes les collectes lancées ! ({success_count}/{total_count})")
                    st.info("📊 Rafraîchissez la page dans 2-3 minutes pour voir les nouvelles données")
                else:
                    st.warning(f"⚠️ {success_count}/{total_count} collectes lancées")
    
    # Boutons individuels
    st.sidebar.markdown("#### Collectes individuelles")
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if st.button("📱 Meta Ads", help="Collecter les campagnes Meta Ads", key="trigger_meta"):
            with st.spinner('Déclenchement...'):
                result = airflow_trigger.trigger_dag('meta_ads_daily_docker')
                if result.get('success'):
                    st.success("✅ Meta Ads lancé")
                else:
                    st.error(f"❌ Échec: {result.get('error')}")
        
        if st.button("🎵 CSV S4A", help="Traiter les CSV Spotify for Artists", key="trigger_s4a"):
            with st.spinner('Déclenchement...'):
                result = airflow_trigger.trigger_dag('s4a_csv_watcher')
                if result.get('success'):
                    st.success("✅ CSV S4A lancé")
                else:
                    st.error(f"❌ Échec: {result.get('error')}")

        if st.button("🎎 CSV Apple", help="Traiter les CSV Apple Music", key="trigger_apple"):
            with st.spinner('Déclenchement...'):
                result = airflow_trigger.trigger_dag('apple_music_csv_watcher')
                if result.get('success'):
                    st.success("✅ CSV Apple lancé")
                else:
                    st.error(f"❌ Échec: {result.get('error')}")
    
    with col2:
        if st.button("🎸 Spotify API", help="Collecter artistes et tracks", key="trigger_spotify"):
            with st.spinner('Déclenchement...'):
                result = airflow_trigger.trigger_dag('spotify_api_daily')
                if result.get('success'):
                    st.success("✅ Spotify API lancé")
                else:
                    st.error(f"❌ Échec: {result.get('error')}")
        
        if st.button("🎬 YouTube", help="Collecter données YouTube", key="trigger_youtube"):
            with st.spinner('Déclenchement...'):
                result = airflow_trigger.trigger_dag('youtube_daily')
                if result.get('success'):
                    st.success("✅ YouTube lancé")
                else:
                    st.error(f"❌ Échec: {result.get('error')}")
        
        if st.button("🔍 Qualité", help="Vérifier la qualité des données", key="trigger_quality"):
            with st.spinner('Déclenchement...'):
                result = airflow_trigger.trigger_dag('data_quality_check')
                if result.get('success'):
                    st.success("✅ Qualité lancée")
                else:
                    st.error(f"❌ Échec: {result.get('error')}")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("💡 **Astuce:** Les collectes prennent 1-3 minutes")


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
        - 📱 **Meta Ads** : Campagnes publicitaires
        - 🎸 **Spotify API** : Artistes, tracks et historique de popularité
        - 🎵 **CSV S4A** : Traitement des fichiers Spotify for Artists
        - 🎎 **CSV Apple** : Traitement des fichiers Apple Music
        - 🎬 **YouTube** : Statistiques de chaîne et vidéos
        - 🔍 **Qualité** : Vérification de la cohérence des données
        
        ### 📊 Sources de données
        - ✅ Meta Ads collecté via API
        - ✅ Spotify API pour artistes, tracks et **historique de popularité quotidien**
        - ✅ Spotify for Artists via CSV (déposez vos fichiers dans `data/raw/spotify_for_artists/`)
        - ✅ Apple Music via CSV (déposez vos fichiers dans `data/raw/apple_music/`)
        - ✅ YouTube via API (données temps réel)
        - ✅ PostgreSQL stockage centralisé
        
        ---
        
        ### 🚀 Comment ça marche ?
        
        1. **Cliquez sur "🚀 Lancer toutes les collectes"** dans la sidebar
        2. Airflow exécute les DAGs en arrière-plan (1-3 minutes)
        3. Rafraîchissez la page pour voir les nouvelles données
        4. Explorez les différentes pages du dashboard
        """)
        
        # Statistiques rapides
        st.markdown("---")
        st.subheader("📊 Aperçu Rapide")
        
        db = get_db()
        
        try:
            col1, col2, col3, col4 = st.columns(4)
            
            # Count Meta Ads
            meta_count = db.get_table_count('meta_campaigns')
            col1.metric("📱 Campagnes Meta", f"{meta_count:,}")
            
            # Count Spotify Artists
            artists_count = db.get_table_count('artists')
            col2.metric("👤 Artistes Spotify", f"{artists_count:,}")
            
            # Count Apple Music
            apple_count = db.get_table_count('apple_songs_performance')
            col3.metric("🎎 Chansons Apple", f"{apple_count:,}")
            
            # Count YouTube
            youtube_count = db.get_table_count('youtube_videos')
            col4.metric("🎬 Vidéos YouTube", f"{youtube_count:,}")
            
            # Deuxième ligne de KPIs
            col1, col2, col3, col4 = st.columns(4)
            
            # Count S4A
            s4a_count = db.get_table_count('s4a_song_timeline')
            col1.metric("🎵 Timeline S4A", f"{s4a_count:,}")
            
            # Count YouTube channel stats
            youtube_channels = db.get_table_count('youtube_channels')
            col2.metric("📺 Chaînes YouTube", f"{youtube_channels:,}")
            
            # Dernière collecte
            last_update_query = """
                SELECT MAX(collected_at) 
                FROM (
                    SELECT collected_at FROM meta_campaigns
                    UNION ALL
                    SELECT collected_at FROM artists
                    UNION ALL
                    SELECT collected_at FROM s4a_songs_global
                    UNION ALL
                    SELECT collected_at FROM apple_songs_performance
                    UNION ALL
                    SELECT collected_at FROM youtube_channels
                ) AS combined
            """
            
            result = db.fetch_query(last_update_query)
            if result and result[0][0]:
                last_update = result[0][0]
                time_diff = datetime.now() - last_update
                hours_ago = int(time_diff.total_seconds() / 3600)
                
                if hours_ago < 1:
                    col3.metric("🕐 Dernière collecte", "< 1h")
                elif hours_ago < 24:
                    col3.metric("🕐 Dernière collecte", f"Il y a {hours_ago}h")
                else:
                    days_ago = int(hours_ago / 24)
                    col3.metric("🕐 Dernière collecte", f"Il y a {days_ago}j")
            else:
                col3.metric("🕐 Dernière collecte", "Aucune")
        
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
        from views.hypeddit import show
        show()
    
    elif page == "apple_music":
        from views.apple_music import show
        show()

    elif page == "youtube":
        from views.youtube import show
        show()


if __name__ == "__main__":
    main()