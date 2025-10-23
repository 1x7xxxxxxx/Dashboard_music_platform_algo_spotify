"""Page d'accueil du dashboard."""
import streamlit as st
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader


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


def show():
    """Affiche la page d'accueil."""
    st.title("🎵 Music Analytics Dashboard")
    st.markdown("---")
    
    st.markdown("""
    ## Bienvenue sur votre Dashboard Musical !
    
    Ce dashboard centralise toutes vos données musicales provenant de :
    - **API Spotify** : Statistiques artistes et tracks
    - **Spotify for Artists** : Streams quotidiens détaillés
    """)
    
    st.markdown("---")
    
    # Stats globales
    st.header("📊 Vue d'ensemble")
    
    db = get_db()
    
    col1, col2, col3 = st.columns(3)
    
    # Artistes suivis
    artists_count = db.get_table_count('artists')
    col1.metric("👤 Artistes suivis", artists_count)
    
    # Tracks
    tracks_count = db.get_table_count('tracks')
    col2.metric("🎵 Tracks", tracks_count)
    
    # Chansons S4A
    s4a_songs = db.get_table_count('s4a_songs_global')
    col3.metric("📊 Chansons S4A", s4a_songs)
    
    st.markdown("---")
    
    # Dernière mise à jour
    st.subheader("🕐 Dernière mise à jour")
    
    last_update_query = """
        SELECT MAX(collected_at) 
        FROM (
            SELECT collected_at FROM artists
            UNION ALL
            SELECT collected_at FROM s4a_songs_global
        ) AS combined
    """
    
    result = db.fetch_query(last_update_query)
    last_update = result[0][0] if result and result[0][0] else "Aucune donnée"
    
    st.info(f"📅 Dernière collecte : {last_update}")
    
    st.markdown("---")
    
    # Navigation
    st.subheader("🧭 Navigation Rapide")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **API Spotify :**
        - 👤 Artist Stats
        - 🎵 Top Tracks
        """)
    
    with col2:
        st.markdown("""
        **Spotify for Artists :**
        - 📊 Vue d'ensemble
        - 🎸 Timeline par chanson
        - 👥 Audience
        """)
    
    db.close()


if __name__ == "__main__":
    show()