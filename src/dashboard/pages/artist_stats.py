"""Page Artist Stats."""
import streamlit as st
import pandas as pd
import plotly.express as px
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
    """Affiche la page Artist Stats."""
    st.title("👤 Statistiques Artistes (API Spotify)")
    st.markdown("---")
    
    db = get_db()
    
    # CORRECTION: Utiliser les VRAIS noms de colonnes
    artists_query = "SELECT artist_id, name, followers, popularity FROM artists ORDER BY followers DESC"
    df_artists = db.fetch_df(artists_query)
    
    if df_artists.empty:
        st.warning("Aucun artiste trouvé. Lancez d'abord la collecte API Spotify.")
        db.close()
        return
    
    # Sélection artiste
    artist_names = df_artists['name'].tolist()
    selected_artist = st.selectbox("Sélectionnez un artiste", artist_names)
    
    artist_data = df_artists[df_artists['name'] == selected_artist].iloc[0]
    
    st.markdown("---")
    
    # KPIs
    col1, col2 = st.columns(2)
    
    col1.metric("👥 Followers", f"{artist_data['followers']:,}")
    col2.metric("🔥 Popularité", f"{artist_data['popularity']}/100")
    
    st.markdown("---")
    
    # Historique - CORRECTION: La table artist_history n'a PAS de colonne 'date'
    st.subheader("📈 Évolution des Followers")
    
    history_query = """
        SELECT collected_at, followers, popularity
        FROM artist_history
        WHERE artist_id = %s
        ORDER BY collected_at
    """
    
    df_history = db.fetch_df(history_query, (artist_data['artist_id'],))
    
    if not df_history.empty:
        df_history['collected_at'] = pd.to_datetime(df_history['collected_at'])
        
        fig = px.line(
            df_history,
            x='collected_at',
            y='followers',
            title=f"Évolution Followers - {selected_artist}",
            labels={'collected_at': 'Date', 'followers': 'Followers'}
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Pas encore d'historique disponible")
    
    db.close()


if __name__ == "__main__":
    show()