"""Page Spotify & S4A - Vue combinée."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sys
from datetime import datetime, timedelta

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
    """Affiche la page Spotify & S4A combinée."""
    st.title("🎵 Spotify & S4A")
    st.markdown("### Analyse complète des performances musicales")
    st.markdown("---")
    
    db = get_db()
    
    # ============================================================================
    # SECTION 1 : KPIs GLOBAUX
    # ============================================================================
    st.header("🎯 Métriques Globales")
    
    col1, col2 = st.columns(2)
    
    # Total chansons
    songs_count = db.get_table_count('s4a_songs_global')
    col1.metric("🎵 Total Chansons", f"{songs_count}")
    
    # Total streams
    total_streams_query = "SELECT SUM(streams) FROM s4a_songs_global"
    total_streams = db.fetch_query(total_streams_query)[0][0] or 0
    col2.metric("🎧 Streams Totaux", f"{total_streams:,}")
    
    st.markdown("---")
    
    # ============================================================================
    # SECTION 2 : TOP 10 CHANSONS PAR STREAMS (avec étiquettes)
    # ============================================================================
    st.header("🏆 Top 10 Chansons par Streams")
    
    top_songs_query = """
        SELECT 
            song,
            streams,
            listeners,
            release_date
        FROM s4a_songs_global
        ORDER BY streams DESC
        LIMIT 10
    """
    
    df_top = db.fetch_df(top_songs_query)
    
    if not df_top.empty:
        # Créer le graphique en barres avec étiquettes
        fig_top = px.bar(
            df_top,
            x='streams',
            y='song',
            orientation='h',
            title="",
            labels={'streams': 'Streams', 'song': 'Chanson'},
            color='streams',
            color_continuous_scale='viridis',
            text='streams'  # Ajouter les étiquettes
        )
        
        # Formater les étiquettes pour afficher les nombres avec séparateurs
        fig_top.update_traces(
            texttemplate='%{text:,.0f}',
            textposition='outside'
        )
        
        fig_top.update_layout(
            height=500,
            showlegend=False,
            xaxis_title='Streams',
            yaxis_title='',
            font=dict(size=12)
        )
        
        st.plotly_chart(fig_top, use_container_width=True)
    else:
        st.warning("⚠️ Aucune donnée disponible")
    
    st.markdown("---")
    
    # ============================================================================
    # SECTION 3 : ÉVOLUTION DE L'AUDIENCE (avec filtres)
    # ============================================================================
    st.header("📈 Évolution de l'Audience")
    
    # Filtres
    st.subheader("🔍 Filtres")
    
    col1, col2 = st.columns(2)
    
    with col1:
        start_date_audience = st.date_input(
            "📅 Date début",
            value=datetime.now().date() - timedelta(days=60),
            key="start_date_audience"
        )
    
    with col2:
        end_date_audience = st.date_input(
            "📅 Date fin",
            value=datetime.now().date(),
            key="end_date_audience"
        )
    
    st.markdown("---")
    
    # Récupérer les données d'audience
    audience_query = """
        SELECT 
            date,
            listeners,
            streams,
            followers
        FROM s4a_audience
        WHERE date >= %s AND date <= %s
        ORDER BY date
    """
    
    df_audience = db.fetch_df(audience_query, (start_date_audience, end_date_audience))
    
    if not df_audience.empty:
        df_audience['date'] = pd.to_datetime(df_audience['date'])
        
        # Graphique multi-lignes avec listeners en JAUNE
        fig_audience = go.Figure()
        
        # Streams (vert Spotify)
        fig_audience.add_trace(go.Scatter(
            x=df_audience['date'],
            y=df_audience['streams'],
            name='Streams',
            mode='lines',
            line=dict(color='#1DB954', width=2),
            fill='tonexty',
            fillcolor='rgba(29, 185, 84, 0.2)'
        ))
        
        # Listeners (JAUNE)
        fig_audience.add_trace(go.Scatter(
            x=df_audience['date'],
            y=df_audience['listeners'],
            name='Listeners',
            mode='lines',
            line=dict(color='#FFD700', width=2)
        ))
        
        # Followers (rouge)
        fig_audience.add_trace(go.Scatter(
            x=df_audience['date'],
            y=df_audience['followers'],
            name='Followers',
            mode='lines',
            line=dict(color='#FF6B6B', width=2)
        ))
        
        fig_audience.update_layout(
            title="Évolution Streams / Listeners / Followers",
            xaxis_title="Date",
            yaxis_title="Nombre",
            height=500,
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        st.plotly_chart(fig_audience, use_container_width=True)
    else:
        st.info("ℹ️ Aucune donnée disponible pour cette période")
    
    st.markdown("---")
    
    # ============================================================================
    # SECTION 4 : ÉVOLUTION DE LA POPULARITÉ SPOTIFY (NOUVEAU)
    # ============================================================================
    st.header("📊 Évolution de l'Index de Popularité Spotify")
    
    # Récupérer la liste des chansons disponibles dans l'historique
    tracks_query = """
        SELECT DISTINCT track_name
        FROM track_popularity_history
        ORDER BY track_name
    """
    
    df_tracks_list = db.fetch_df(tracks_query)
    
    if not df_tracks_list.empty:
        # Filtres
        st.subheader("🔍 Filtres")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            # Dropdown des chansons
            selected_track = st.selectbox(
                "🎵 Sélectionner une chanson",
                options=df_tracks_list['track_name'].tolist(),
                key="track_selector_popularity"
            )
        
        with col2:
            # Date début
            start_date_pop = st.date_input(
                "📅 Date début",
                value=datetime.now().date() - timedelta(days=30),
                format="DD/MM/YYYY",
                key="start_date_popularity"
            )
        
        with col3:
            # Date fin
            end_date_pop = st.date_input(
                "📅 Date fin",
                value=datetime.now().date(),
                format="DD/MM/YYYY",
                key="end_date_popularity"
            )
        
        st.markdown("---")
        
        # Récupérer l'historique de popularité pour la chanson sélectionnée
        popularity_query = """
            SELECT date, popularity
            FROM track_popularity_history
            WHERE track_name = %s
            ORDER BY date
        """
        df_popularity = db.fetch_df(
            popularity_query,
            (selected_track,)
        )

        # Afficher la période couverte
        if not df_popularity.empty:
            st.info(f"📅 Période : {df_popularity['date'].min()} → {df_popularity['date'].max()}")
        
        df_popularity = db.fetch_df(
            popularity_query,
            (selected_track, start_date_pop, end_date_pop)
        )
        
        if not df_popularity.empty:
            df_popularity['date'] = pd.to_datetime(df_popularity['date'])
            
            # Créer le graphique de popularité
            fig_pop = go.Figure()
            
            fig_pop.add_trace(go.Scatter(
                x=df_popularity['date'],
                y=df_popularity['popularity'],
                name='Popularité',
                mode='lines+markers',
                line=dict(color='#1DB954', width=3),
                marker=dict(size=8, symbol='circle'),
                fill='tozeroy',
                fillcolor='rgba(29, 185, 84, 0.2)',
                hovertemplate='<b>Date:</b> %{x|%d/%m/%Y}<br><b>Popularité:</b> %{y}/100<extra></extra>'
            ))
            
            fig_pop.update_layout(
                title=f"Évolution de la popularité : {selected_track}",
                xaxis_title="Date",
                yaxis_title="Index de Popularité (0-100)",
                height=500,
                hovermode='x unified',
                yaxis=dict(range=[0, 100]),
                showlegend=False
            )
            
            st.plotly_chart(fig_pop, use_container_width=True)
            
            # Statistiques de la période
            col1, col2, col3 = st.columns(3)
            
            avg_pop = df_popularity['popularity'].mean()
            col1.metric(
                "📊 Popularité Moyenne",
                f"{avg_pop:.1f}/100"
            )
            
            max_pop = df_popularity['popularity'].max()
            max_date = df_popularity[df_popularity['popularity'] == max_pop]['date'].iloc[0]
            col2.metric(
                "🔥 Maximum",
                f"{int(max_pop)}/100",
                f"Le {max_date.strftime('%d/%m/%Y')}"
            )
            
            min_pop = df_popularity['popularity'].min()
            min_date = df_popularity[df_popularity['popularity'] == min_pop]['date'].iloc[0]
            col3.metric(
                "📉 Minimum",
                f"{int(min_pop)}/100",
                f"Le {min_date.strftime('%d/%m/%Y')}"
            )
            
        else:
            st.info(f"ℹ️ Aucune donnée de popularité disponible pour '{selected_track}' sur cette période")
    else:
        st.warning("⚠️ Aucune donnée d'historique de popularité disponible")
        st.info("""
        **Pour commencer à collecter l'historique de popularité :**
        
        1. Lancez la collecte Spotify API depuis la page d'accueil
        2. Le DAG `spotify_api_daily` collectera automatiquement les données de popularité
        3. Revenez ici pour visualiser l'évolution
        """)
    
    # Footer
    st.markdown("---")
    st.caption(f"📊 Dernière mise à jour : {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    db.close()


if __name__ == "__main__":
    show()