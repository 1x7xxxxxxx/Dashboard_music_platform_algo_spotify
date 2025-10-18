"""Page des statistiques des artistes."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Ajouter le répertoire parent au path
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from src.utils.config_loader import config_loader
from src.database.postgresql_handler import PostgreSQLHandler

st.set_page_config(page_title="Artist Stats", page_icon="📊", layout="wide")

st.title("📊 Statistiques des Artistes")

# Connexion DB
@st.cache_resource
def get_db_connection():
    config = config_loader.load()
    db_config = config['database']
    return PostgreSQLHandler(
        host=db_config['host'],
        port=db_config['port'],
        database=db_config['database'],
        user=db_config['user'],
        password=db_config['password']
    )

db = get_db_connection()

# Récupérer la liste des artistes
@st.cache_data(ttl=300)
def get_artists():
    with db.get_connection() as conn:
        query = "SELECT artist_id, name, followers, popularity, genres FROM artists ORDER BY name;"
        df = pd.read_sql(query, conn)
    return df

try:
    artists_df = get_artists()
    
    if artists_df.empty:
        st.warning("⚠️ Aucun artiste dans la base de données. Lancez d'abord `collect_and_store.py`")
        st.stop()
    
    # Sélecteur d'artiste
    selected_artist_name = st.selectbox(
        "Sélectionnez un artiste",
        options=artists_df['name'].tolist(),
        index=0
    )
    
    artist_data = artists_df[artists_df['name'] == selected_artist_name].iloc[0]
    artist_id = artist_data['artist_id']
    
    st.markdown("---")
    
    # Métriques actuelles
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="👥 Followers",
            value=f"{artist_data['followers']:,}",
        )
    
    with col2:
        st.metric(
            label="🔥 Popularité",
            value=f"{artist_data['popularity']}/100",
        )
    
    with col3:
        genres = artist_data['genres']
        genre_text = ", ".join(genres) if genres else "N/A"
        st.metric(
            label="🎸 Genres",
            value=genre_text[:20] + "..." if len(genre_text) > 20 else genre_text
        )
    
    st.markdown("---")
    
    # Récupérer l'historique
    @st.cache_data(ttl=300)
    def get_artist_history(artist_id, days=30):
        with db.get_connection() as conn:
            query = """
                SELECT 
                    DATE(collected_at) as date,
                    AVG(followers) as followers,
                    AVG(popularity) as popularity
                FROM artist_history
                WHERE artist_id = %s 
                AND collected_at >= NOW() - INTERVAL '%s days'
                GROUP BY DATE(collected_at)
                ORDER BY date;
            """
            df = pd.read_sql(query, conn, params=(artist_id, days))
        return df
    
    # Slider pour choisir la période
    days = st.slider("Période d'analyse (jours)", min_value=7, max_value=90, value=30)
    
    history_df = get_artist_history(artist_id, days)
    
    if not history_df.empty:
        # Graphique d'évolution des followers
        st.subheader("📈 Évolution des Followers")
        fig_followers = px.line(
            history_df,
            x='date',
            y='followers',
            title=f"Followers de {selected_artist_name}",
            labels={'date': 'Date', 'followers': 'Nombre de Followers'},
            markers=True
        )
        fig_followers.update_layout(hovermode='x unified')
        st.plotly_chart(fig_followers, use_container_width=True)
        
        # Graphique d'évolution de la popularité
        st.subheader("🔥 Évolution de la Popularité")
        fig_popularity = px.line(
            history_df,
            x='date',
            y='popularity',
            title=f"Popularité de {selected_artist_name}",
            labels={'date': 'Date', 'popularity': 'Score de Popularité'},
            markers=True,
            color_discrete_sequence=['#FF6B6B']
        )
        fig_popularity.update_layout(hovermode='x unified')
        st.plotly_chart(fig_popularity, use_container_width=True)
        
        # Statistiques de variation
        if len(history_df) >= 2:
            first_followers = history_df.iloc[0]['followers']
            last_followers = history_df.iloc[-1]['followers']
            followers_change = last_followers - first_followers
            followers_change_pct = (followers_change / first_followers * 100) if first_followers > 0 else 0
            
            st.subheader("📊 Variations sur la période")
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric(
                    label="Variation Followers",
                    value=f"{int(last_followers):,}",
                    delta=f"{int(followers_change):,} ({followers_change_pct:+.1f}%)"
                )
            
            with col2:
                first_pop = history_df.iloc[0]['popularity']
                last_pop = history_df.iloc[-1]['popularity']
                pop_change = last_pop - first_pop
                st.metric(
                    label="Variation Popularité",
                    value=f"{int(last_pop)}/100",
                    delta=f"{pop_change:+.1f}"
                )
    else:
        st.info("📊 Pas encore assez de données historiques. Lancez la collecte quotidiennement pour voir l'évolution !")
    
    # Informations supplémentaires
    with st.expander("ℹ️ Informations sur les métriques"):
        st.markdown("""
        - **Followers** : Nombre total d'abonnés sur Spotify
        - **Popularité** : Score de 0 à 100 calculé par Spotify basé sur l'écoute récente
        - **Genres** : Catégories musicales associées à l'artiste
        
        Les données sont collectées quotidiennement via le pipeline ETL.
        """)

except Exception as e:
    st.error(f"❌ Erreur: {e}")
    st.info("💡 Vérifiez la connexion à la base de données")