"""Page Top Tracks."""
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
    """Affiche la page Top Tracks."""
    st.title("🎵 Top Tracks (API Spotify)")
    st.markdown("---")
    
    db = get_db()
    
    # CORRECTION: Utiliser track_name au lieu de name
    tracks_query = """
        SELECT 
            track_name,
            popularity,
            duration_ms,
            album_name,
            release_date
        FROM tracks
        ORDER BY popularity DESC
        LIMIT 20
    """
    
    df_tracks = db.fetch_df(tracks_query)
    
    if df_tracks.empty:
        st.warning("Aucune track trouvée. Lancez d'abord la collecte API Spotify.")
        db.close()
        return
    
    # Convertir durée
    df_tracks['duration_min'] = df_tracks['duration_ms'] / 60000
    
    # Top 10
    st.subheader("🏆 Top 10 Tracks par Popularité")
    
    df_top10 = df_tracks.head(10)
    
    fig = px.bar(
        df_top10,
        x='popularity',
        y='track_name',
        orientation='h',
        title="Top 10 Tracks",
        labels={'popularity': 'Popularité', 'track_name': 'Track'},
        color='popularity',
        color_continuous_scale='viridis'
    )
    
    fig.update_layout(height=500, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Tableau complet
    st.subheader("📋 Liste Complète des Tracks")
    
    df_display = df_tracks[['track_name', 'album_name', 'popularity', 'duration_min', 'release_date']].copy()
    df_display['release_date'] = pd.to_datetime(df_display['release_date']).dt.strftime('%Y-%m-%d')
    
    st.dataframe(
        df_display.rename(columns={
            'track_name': 'Track',
            'album_name': 'Album',
            'popularity': 'Popularité',
            'duration_min': 'Durée (min)',
            'release_date': 'Date sortie'
        }),
        hide_index=True,
        use_container_width=True
    )
    
    db.close()


if __name__ == "__main__":
    show()