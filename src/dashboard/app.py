"""Application Streamlit principale."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sys
from datetime import datetime, timedelta

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader

# Configuration de la page
st.set_page_config(
    page_title="Music Platform Dashboard",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
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


def main():
    """Page principale."""
    # Navigation
    st.sidebar.title("🎵 Navigation")
    
    pages = {
        "🏠 Accueil": "home",
        "📱 Meta Ads - Vue d'ensemble": "meta_ads_overview",
        "📊 S4A - Vue d'ensemble": "s4a_overview",
        "🎸 S4A - Timeline par chanson": "s4a_song_timeline",
        "👤 Artist Stats": "artist_stats",
        "🎵 Top Tracks": "top_tracks",
        "📊 S4A - Audience": "s4a_audience",
    }
    
    selection = st.sidebar.radio("Aller à", list(pages.keys()))
    
    # Charger la page sélectionnée
    page = pages[selection]
    
    if page == "home":
        st.title("🎵 Music Platform Dashboard")
        st.markdown("---")
        
        st.markdown("""
        ## 🎯 Bienvenue sur votre Dashboard Musical !
        
        ### 📱 Meta Ads
        - Vue d'ensemble des campagnes actives
        
        ### 🎸 Spotify for Artists
        - Statistiques globales par chanson
        - Timeline détaillée des streams
        - Statistiques d'audience
        
        ### 👤 Stats Artiste
        - Analyse complète des performances
        
        ---
        
        ### 🚀 Système Opérationnel
        - ✅ Meta Ads collecté automatiquement
        - ✅ Spotify for Artists avec téléchargement manuel + auto-intégration
        - ✅ PostgreSQL stockage centralisé (11,231+ enregistrements)
        - ✅ Dashboard interactif Streamlit
        """)
        
        # Statistiques rapides
        st.markdown("---")
        st.subheader("📊 Aperçu Rapide")
        
        db = get_db()
        
        try:
            # Count Meta Ads
            meta_count = db.get_table_count('meta_ads_campaigns')
            
            # Count S4A
            s4a_count = db.get_table_count('s4a_song_timeline')
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("📱 Campagnes Meta Ads", f"{meta_count:,}")
            
            with col2:
                st.metric("🎵 Enregistrements S4A", f"{s4a_count:,}")
        
        finally:
            db.close()
    
    elif page == "meta_ads_overview":
        # Importer le module
        from pages.meta_ads_overview import show
        show()
    
    elif page == "s4a_overview":
        from pages.s4a_overview import show
        show()
    
    elif page == "s4a_song_timeline":
        from pages.s4a_song_timeline import show
        show()
    
    elif page == "artist_stats":
        from pages.artist_stats import show
        show()
    
    elif page == "top_tracks":
        from pages.top_tracks import show
        show()
    
    elif page == "s4a_audience":
        from pages.s4a_audience import show
        show()


if __name__ == "__main__":
    main()