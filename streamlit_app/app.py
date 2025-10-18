"""Dashboard Streamlit - Page d'accueil."""
import streamlit as st
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from src.utils.config_loader import config_loader
from src.database.postgresql_handler import PostgreSQLHandler

# Configuration de la page
st.set_page_config(
    page_title="Spotify ETL Dashboard",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styles CSS personnalisés
st.markdown("""
    <style>
    .main-title {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        color: #1DB954;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# Titre principal
st.markdown('<h1 class="main-title">🎵 Spotify ETL Dashboard</h1>', unsafe_allow_html=True)

st.markdown("---")

# Introduction
st.markdown("""
## 👋 Bienvenue sur votre Dashboard Analytics Spotify

Ce dashboard vous permet de suivre et analyser les performances de vos artistes sur Spotify en temps réel.

### 📊 Fonctionnalités disponibles :

- **📈 Artist Stats** : Statistiques détaillées et évolution des followers/popularité
- **🎵 Top Tracks** : Analyse des meilleurs titres et leur performance
- **📊 Historique** : Suivi quotidien de l'évolution des métriques

### 🔄 Données actualisées quotidiennement via pipeline ETL automatisé
""")

st.markdown("---")

# Connexion à la base de données
@st.cache_resource
def get_db_connection():
    """Crée une connexion à la base de données."""
    config = config_loader.load()
    db_config = config['database']
    
    return PostgreSQLHandler(
        host=db_config['host'],
        port=db_config['port'],
        database=db_config['database'],
        user=db_config['user'],
        password=db_config['password']
    )

try:
    db = get_db_connection()
    
    # Récupérer les stats globales
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            # Nombre total d'artistes
            cur.execute("SELECT COUNT(*) FROM artists;")
            total_artists = cur.fetchone()[0]
            
            # Nombre total de tracks
            cur.execute("SELECT COUNT(*) FROM tracks;")
            total_tracks = cur.fetchone()[0]
            
            # Dernière collecte
            cur.execute("SELECT MAX(collected_at) FROM artists;")
            last_update = cur.fetchone()[0]
    
    # Afficher les métriques
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="👥 Artistes suivis",
            value=total_artists,
        )
    
    with col2:
        st.metric(
            label="🎵 Tracks collectés",
            value=total_tracks,
        )
    
    with col3:
        st.metric(
            label="🕐 Dernière mise à jour",
            value=last_update.strftime("%d/%m/%Y %H:%M") if last_update else "N/A",
        )
    
    st.markdown("---")
    
    # Instructions
    st.info("👈 Utilisez le menu latéral pour naviguer entre les différentes pages du dashboard.")
    
    # Footer
    st.markdown("---")
    st.markdown("""
        <div style='text-align: center; color: gray; padding: 20px;'>
            <p>🎵 Spotify ETL Dashboard | Données collectées via API Spotify</p>
        </div>
    """, unsafe_allow_html=True)
    
except Exception as e:
    st.error(f"❌ Erreur de connexion à la base de données: {e}")
    st.info("💡 Assurez-vous que PostgreSQL est démarré et que les credentials sont corrects dans config.yaml")