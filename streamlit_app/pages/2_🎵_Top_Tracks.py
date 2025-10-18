"""Page d'analyse des top tracks."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from src.utils.config_loader import config_loader
from src.database.postgresql_handler import PostgreSQLHandler

st.set_page_config(page_title="Top Tracks", page_icon="🎵", layout="wide")

st.title("🎵 Analyse des Top Tracks")

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
        query = "SELECT artist_id, name FROM artists ORDER BY name;"
        df = pd.read_sql(query, conn)
    return df

try:
    artists_df = get_artists()
    
    if artists_df.empty:
        st.warning("⚠️ Aucun artiste dans la base de données.")
        st.stop()
    
    # Sélecteur d'artiste
    selected_artist_name = st.selectbox(
        "Sélectionnez un artiste",
        options=artists_df['name'].tolist(),
        index=0
    )
    
    artist_id = artists_df[artists_df['name'] == selected_artist_name].iloc[0]['artist_id']
    
    st.markdown("---")
    
    # Récupérer les tracks de l'artiste
    @st.cache_data(ttl=300)
    def get_tracks(artist_id):
        with db.get_connection() as conn:
            query = """
                SELECT 
                    track_id,
                    track_name,
                    popularity,
                    duration_ms,
                    explicit,
                    album_name,
                    release_date,
                    collected_at
                FROM tracks
                WHERE artist_id = %s
                ORDER BY popularity DESC;
            """
            df = pd.read_sql(query, conn, params=(artist_id,))
        return df
    
    tracks_df = get_tracks(artist_id)
    
    if tracks_df.empty:
        st.warning(f"⚠️ Aucun track trouvé pour {selected_artist_name}")
        st.stop()
    
    # Métriques globales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="🎵 Total Tracks",
            value=len(tracks_df)
        )
    
    with col2:
        avg_popularity = tracks_df['popularity'].mean()
        st.metric(
            label="📊 Popularité Moyenne",
            value=f"{avg_popularity:.1f}/100"
        )
    
    with col3:
        avg_duration = tracks_df['duration_ms'].mean() / 1000 / 60  # en minutes
        st.metric(
            label="⏱️ Durée Moyenne",
            value=f"{avg_duration:.1f} min"
        )
    
    with col4:
        explicit_count = tracks_df['explicit'].sum()
        st.metric(
            label="🔞 Tracks Explicit",
            value=f"{explicit_count}"
        )
    
    st.markdown("---")
    
    # TOP 10 Tracks
    st.subheader("🏆 Top 10 Tracks par Popularité")
    
    top_10 = tracks_df.head(10).copy()
    top_10['duration_min'] = (top_10['duration_ms'] / 1000 / 60).round(2)
    
    # Graphique en barres
    fig_top10 = px.bar(
        top_10,
        x='popularity',
        y='track_name',
        orientation='h',
        title=f"Top 10 des tracks de {selected_artist_name}",
        labels={'popularity': 'Popularité', 'track_name': 'Track'},
        color='popularity',
        color_continuous_scale='Viridis',
        text='popularity'
    )
    fig_top10.update_layout(
        yaxis={'categoryorder': 'total ascending'},
        showlegend=False,
        height=500
    )
    fig_top10.update_traces(texttemplate='%{text}/100', textposition='outside')
    st.plotly_chart(fig_top10, use_container_width=True)
    
    # Tableau détaillé
    st.subheader("📋 Liste Complète des Tracks")
    
    # Préparer le dataframe pour l'affichage
    display_df = tracks_df.copy()
    display_df['duration_min'] = (display_df['duration_ms'] / 1000 / 60).round(2)
    display_df['explicit'] = display_df['explicit'].map({True: '🔞', False: '✅'})
    display_df['release_date'] = pd.to_datetime(display_df['release_date']).dt.strftime('%Y-%m-%d')
    
    # Colonnes à afficher
    display_columns = {
        'track_name': 'Titre',
        'popularity': 'Popularité',
        'duration_min': 'Durée (min)',
        'explicit': 'Explicit',
        'album_name': 'Album',
        'release_date': 'Sortie'
    }
    
    st.dataframe(
        display_df[list(display_columns.keys())].rename(columns=display_columns),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Popularité": st.column_config.ProgressColumn(
                "Popularité",
                help="Score de popularité Spotify (0-100)",
                format="%d/100",
                min_value=0,
                max_value=100,
            ),
        }
    )
    
    st.markdown("---")
    
    # Distribution de la popularité
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Distribution de la Popularité")
        fig_dist = px.histogram(
            tracks_df,
            x='popularity',
            nbins=20,
            title="Répartition des scores de popularité",
            labels={'popularity': 'Popularité', 'count': 'Nombre de tracks'},
            color_discrete_sequence=['#1DB954']
        )
        st.plotly_chart(fig_dist, use_container_width=True)
    
    with col2:
        st.subheader("⏱️ Distribution des Durées")
        tracks_df['duration_min'] = tracks_df['duration_ms'] / 1000 / 60
        fig_duration = px.histogram(
            tracks_df,
            x='duration_min',
            nbins=15,
            title="Répartition des durées (minutes)",
            labels={'duration_min': 'Durée (min)', 'count': 'Nombre de tracks'},
            color_discrete_sequence=['#FF6B6B']
        )
        st.plotly_chart(fig_duration, use_container_width=True)
    
    # Analyse par album
    st.subheader("💿 Tracks par Album")
    
    albums_count = tracks_df.groupby('album_name').agg({
        'track_id': 'count',
        'popularity': 'mean'
    }).reset_index()
    albums_count.columns = ['Album', 'Nombre de Tracks', 'Popularité Moyenne']
    albums_count = albums_count.sort_values('Popularité Moyenne', ascending=False)
    
    fig_albums = px.bar(
        albums_count,
        x='Album',
        y='Nombre de Tracks',
        color='Popularité Moyenne',
        title="Nombre de tracks et popularité moyenne par album",
        labels={'Nombre de Tracks': 'Tracks', 'Popularité Moyenne': 'Pop. Moy.'},
        color_continuous_scale='RdYlGn'
    )
    fig_albums.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_albums, use_container_width=True)
    
    # Statistiques supplémentaires
    with st.expander("📈 Statistiques Détaillées"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("🏆 Track le plus populaire", 
                     tracks_df.iloc[0]['track_name'][:30] + "..." if len(tracks_df.iloc[0]['track_name']) > 30 else tracks_df.iloc[0]['track_name'])
            st.metric("Score", f"{tracks_df.iloc[0]['popularity']}/100")
        
        with col2:
            st.metric("📉 Track le moins populaire", 
                     tracks_df.iloc[-1]['track_name'][:30] + "..." if len(tracks_df.iloc[-1]['track_name']) > 30 else tracks_df.iloc[-1]['track_name'])
            st.metric("Score", f"{tracks_df.iloc[-1]['popularity']}/100")
        
        with col3:
            st.metric("📊 Écart de popularité", 
                     f"{tracks_df['popularity'].max() - tracks_df['popularity'].min()} points")
            st.metric("Médiane", f"{tracks_df['popularity'].median():.0f}/100")
    
    # Informations
    with st.expander("ℹ️ À propos des métriques"):
        st.markdown("""
        - **Popularité** : Score de 0 à 100 calculé par Spotify basé sur les écoutes récentes
        - **Durée** : Durée totale du track en minutes
        - **Explicit** : 🔞 = contenu explicite, ✅ = tout public
        - **Date de sortie** : Date de publication du track
        
        💡 Les données sont mises à jour quotidiennement via le pipeline ETL.
        """)
    
    # Source et date
    st.markdown("---")
    last_update = tracks_df['collected_at'].max()
    st.caption(f"📅 Dernière mise à jour : {last_update.strftime('%d/%m/%Y à %H:%M')}")
    st.caption("📊 Source : API Spotify")

except Exception as e:
    st.error(f"❌ Erreur: {e}")
    import traceback
    st.code(traceback.format_exc())