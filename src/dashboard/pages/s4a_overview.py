"""Page Vue d'ensemble Spotify for Artists."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
    """Affiche la page Vue d'ensemble S4A."""
    st.title("📊 Spotify for Artists - Vue d'ensemble")
    st.markdown("---")
    
    # Connexion DB
    db = get_db()
    
    # KPIs globaux
    st.header("🎯 Métriques Globales")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Total chansons
    songs_count = db.get_table_count('s4a_songs_global')
    col1.metric("🎵 Total Chansons", f"{songs_count}")
    
    # Total streams
    total_streams_query = "SELECT SUM(streams) FROM s4a_songs_global"
    total_streams = db.fetch_query(total_streams_query)[0][0] or 0
    col2.metric("🎧 Streams Totaux", f"{total_streams:,}")
    
    # Total saves
    total_saves_query = "SELECT SUM(saves) FROM s4a_songs_global"
    total_saves = db.fetch_query(total_saves_query)[0][0] or 0
    col3.metric("❤️ Total Saves", f"{total_saves:,}")
    
    # Jours de données
    days_count = db.get_table_count('s4a_audience')
    col4.metric("📅 Jours de données", f"{days_count}")
    
    st.markdown("---")
    
    # Top chansons
    st.header("🏆 Top 10 Chansons")
    
    top_songs_query = """
        SELECT 
            song,
            streams,
            listeners,
            saves,
            release_date
        FROM s4a_songs_global
        ORDER BY streams DESC
        LIMIT 10
    """
    
    df_top = db.fetch_df(top_songs_query)
    
    if not df_top.empty:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Graphique en barres
            fig = px.bar(
                df_top,
                x='streams',
                y='song',
                orientation='h',
                title="Top 10 par Streams",
                labels={'streams': 'Streams', 'song': 'Chanson'},
                color='streams',
                color_continuous_scale='viridis'
            )
            fig.update_layout(height=500, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Tableau
            st.dataframe(
                df_top[['song', 'streams', 'saves']],
                hide_index=True,
                use_container_width=True
            )
    
    st.markdown("---")
    
    # Évolution audience globale
    st.header("📈 Évolution de l'Audience")
    
    audience_query = """
        SELECT 
            date,
            listeners,
            streams,
            followers
        FROM s4a_audience
        ORDER BY date
    """
    
    df_audience = db.fetch_df(audience_query)
    
    if not df_audience.empty:
        df_audience['date'] = pd.to_datetime(df_audience['date'])
        
        # Graphique multi-lignes
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df_audience['date'],
            y=df_audience['streams'],
            name='Streams',
            mode='lines',
            line=dict(color='#1DB954', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=df_audience['date'],
            y=df_audience['listeners'],
            name='Listeners',
            mode='lines',
            line=dict(color='#1ed760', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=df_audience['date'],
            y=df_audience['followers'],
            name='Followers',
            mode='lines',
            line=dict(color='#ff6b6b', width=2)
        ))
        
        fig.update_layout(
            title="Évolution Streams / Listeners / Followers",
            xaxis_title="Date",
            yaxis_title="Nombre",
            height=500,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Stats derniers 30 jours
        st.subheader("📊 Statistiques 30 derniers jours")
        
        df_last_30 = df_audience.tail(30)
        
        col1, col2, col3 = st.columns(3)
        
        avg_streams = df_last_30['streams'].mean()
        col1.metric("Moy. Streams/jour", f"{avg_streams:,.0f}")
        
        avg_listeners = df_last_30['listeners'].mean()
        col2.metric("Moy. Listeners/jour", f"{avg_listeners:,.0f}")
        
        current_followers = df_audience['followers'].iloc[-1]
        col3.metric("Followers actuels", f"{current_followers:,}")
    
    db.close()


if __name__ == "__main__":
    show()