"""Page META x SPOTIFY - Corrélation des performances."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from src.dashboard.utils import get_db_connection

def get_available_songs():
    """Récupère la liste des chansons avec mapping actif."""
    db = get_db_connection()
    
    # ✅ CORRECTION : Utilisation de s4a_song_timeline au lieu de s4a_songs_global
    query = """
        WITH total_streams_per_song AS (
            SELECT song, SUM(streams) as total_streams
            FROM s4a_song_timeline
            GROUP BY song
        )
        SELECT DISTINCT
            m.song,
            COUNT(DISTINCT m.campaign_id) as campaigns_count,
            MAX(t.popularity) as max_popularity,
            COALESCE(ts.total_streams, 0) as total_streams
        FROM meta_spotify_mapping m
        LEFT JOIN tracks t ON m.track_id = t.track_id
        LEFT JOIN total_streams_per_song ts ON m.song = ts.song
        WHERE m.is_active = true
        GROUP BY m.song, ts.total_streams
        ORDER BY total_streams DESC NULLS LAST
    """
    
    df = db.fetch_df(query)
    db.close()
    
    return df


def get_combined_data(song: str, start_date, end_date):
    """
    Récupère les données combinées META + SPOTIFY pour une chanson.
    """
    db = get_db_connection()
    
    query = """
        WITH date_range AS (
            SELECT generate_series(
                %s::date,
                %s::date,
                '1 day'::interval
            )::date as date
        ),
        
        -- Streams quotidiens depuis S4A
        daily_streams AS (
            SELECT 
                st.date,
                st.streams
            FROM s4a_song_timeline st
            WHERE st.song = %s
                AND st.date >= %s
                AND st.date <= %s
        ),
        
        -- Popularité depuis Spotify API (dernière valeur collectée)
        track_popularity AS (
            SELECT 
                t.popularity
            FROM tracks t
            JOIN meta_spotify_mapping m ON t.track_id = m.track_id
            WHERE m.song = %s
                AND m.is_active = true
            ORDER BY t.collected_at DESC
            LIMIT 1
        ),
        
        -- Conversions quotidiennes depuis Meta
        daily_conversions AS (
            SELECT 
                i.date,
                SUM(i.conversions) as conversions
            FROM meta_insights i
            JOIN meta_ads a ON i.ad_id = a.ad_id
            JOIN meta_spotify_mapping m ON a.campaign_id = m.campaign_id
            WHERE m.song = %s
                AND m.is_active = true
                AND i.date >= %s
                AND i.date <= %s
            GROUP BY i.date
        )
        
        SELECT 
            dr.date,
            COALESCE(ds.streams, 0) as streams,
            COALESCE(tp.popularity, 0) as popularity,
            COALESCE(dc.conversions, 0) as conversions
        FROM date_range dr
        LEFT JOIN daily_streams ds ON dr.date = ds.date
        CROSS JOIN track_popularity tp
        LEFT JOIN daily_conversions dc ON dr.date = dc.date
        ORDER BY dr.date
    """
    
    df = db.fetch_df(
        query, 
        (start_date, end_date, song, start_date, end_date, song, song, start_date, end_date)
    )
    
    db.close()
    return df


def show():
    """Affiche la page META x SPOTIFY."""
    st.title("🎵 META x SPOTIFY")
    st.markdown("### Corrélation des performances publicitaires et musicales")
    st.markdown("---")
    
    db = get_db_connection()
    
    # Vérifier la table de mapping
    if not db.table_exists('meta_spotify_mapping'):
        st.error("❌ Table de mapping non trouvée")
        st.info("Veuillez créer la table de mapping via le script `create_mapping_table.py`.")
        db.close()
        return
    
    # Récupérer les chansons
    df_songs = get_available_songs()
    
    if df_songs.empty:
        st.warning("⚠️ Aucun mapping campagne ↔ chanson trouvé")
        st.info("Utilisez `python scripts/manage_mapping.py` pour lier vos campagnes.")
        db.close()
        return
    
    # FILTRES
    st.header("🔍 Filtres")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        selected_song = st.selectbox("🎵 Sélectionner une chanson", df_songs['song'].tolist())
    
    with col2:
        start_date = st.date_input("📅 Début", datetime.now().date() - timedelta(days=30))
    
    with col3:
        end_date = st.date_input("📅 Fin", datetime.now().date())
    
    st.markdown("---")
    
    # INFOS CHANSON
    song_info = df_songs[df_songs['song'] == selected_song].iloc[0]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("🎯 Campagnes Liées", int(song_info['campaigns_count']))
    col2.metric("📊 Popularité", f"{int(song_info['max_popularity'] or 0)}/100")
    col3.metric("🎧 Streams Totaux (Timeline)", f"{int(song_info['total_streams']):,}")
    
    st.markdown("---")
    
    # DONNÉES COMBINÉES
    df_data = get_combined_data(selected_song, start_date, end_date)
    
    if df_data.empty:
        st.warning(f"⚠️ Aucune donnée pour '{selected_song}' sur cette période")
        db.close()
        return
    
    df_data['date'] = pd.to_datetime(df_data['date'])
    
    # GRAPHIQUE
    st.header("📈 Performance Croisée")
    fig = go.Figure()
    
    # Streams (Aire verte)
    fig.add_trace(go.Scatter(
        x=df_data['date'], y=df_data['streams'], name='Streams',
        mode='lines', fill='tozeroy', fillcolor='rgba(29, 185, 84, 0.3)',
        line=dict(color='#1DB954', width=2), yaxis='y'
    ))
    
    # Popularité (Ligne orange)
    fig.add_trace(go.Scatter(
        x=df_data['date'], y=df_data['popularity'], name='Popularité',
        mode='lines', line=dict(color='#FF9500', width=3, dash='dot'),
        yaxis='y2'
    ))
    
    # Conversions (Ligne rouge)
    fig.add_trace(go.Scatter(
        x=df_data['date'], y=df_data['conversions'], name='Conversions Meta',
        mode='lines+markers', line=dict(color='#FF3B30', width=2),
        yaxis='y3'
    ))
    
    fig.update_layout(
        title=f"Performance : {selected_song}",
        xaxis=dict(title='Date'),
        yaxis=dict(title='Streams', side='left', showgrid=True),
        yaxis2=dict(title='Popularité', side='right', overlaying='y', showgrid=False, range=[0, 100]),
        yaxis3=dict(title='Conversions', side='right', overlaying='y', anchor='free', position=0.95, showgrid=False),
        height=600, hovermode='x unified',
        legend=dict(orientation="h", y=1.02, x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # STATS PÉRIODE
    st.header("📊 Statistiques de la période")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Streams Totaux", f"{df_data['streams'].sum():,.0f}")
    c2.metric("Moy. Streams/jour", f"{df_data['streams'].mean():,.0f}")
    c3.metric("Conversions Totales", f"{int(df_data['conversions'].sum()):,}")
    c4.metric("Popularité Actuelle", f"{int(df_data['popularity'].iloc[-1])}/100")
    
    # CORRÉLATION
    st.markdown("---")
    st.header("🔬 Analyse de Corrélation")
    
    if df_data['conversions'].sum() > 0 and df_data['streams'].sum() > 0:
        df_corr = df_data[(df_data['conversions'] > 0) & (df_data['streams'] > 0)]
        if len(df_corr) > 2:
            corr = df_corr[['conversions', 'streams']].corr().iloc[0, 1]
            c1, c2, c3 = st.columns(3)
            c1.metric("Corrélation", f"{corr:.2f}")
            
            if corr > 0.7: interpretation = "🟢 Forte"
            elif corr > 0.3: interpretation = "🟡 Modérée"
            elif corr > -0.3: interpretation = "⚪ Faible/Nulle"
            else: interpretation = "🔴 Négative"
            
            c2.metric("Interprétation", interpretation)
            c3.info("Calculé sur les jours avec >0 conversion.")
        else:
            st.info("Pas assez de données pour la corrélation.")
    else:
        st.info("Pas de conversions ou streams sur cette période.")

    db.close()

if __name__ == "__main__":
    show()