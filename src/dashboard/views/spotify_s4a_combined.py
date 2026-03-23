"""Page Spotify & S4A - Vue consolidée et nettoyée."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from src.dashboard.utils import get_db_connection
from src.dashboard.auth import artist_id_sql_filter

# ⚠️ IMPORTANT : Le nom exact tel qu'il apparaît dans tes CSV pour la ligne "Total"
ARTIST_NAME_FILTER = "1x7xxxxxxx" 

def show():
    """Affiche la page Spotify & S4A combinée."""
    st.title("🎵 Spotify & S4A")
    st.markdown("### Analyse des performances (Source : Timeline CSV)")
    st.markdown("---")
    
    db = get_db_connection()
    artist_frag, artist_params = artist_id_sql_filter()

    # ============================================================================
    # 1. RÉCUPÉRATION DES DONNÉES GLOBALES (DÉDUPLIQUÉES)
    # ============================================================================

    # A. Date de mise à jour
    update_query = f"SELECT MAX(collected_at) FROM s4a_song_timeline WHERE 1=1 {artist_frag}"
    last_update_res = db.fetch_query(update_query, artist_params)
    last_update = last_update_res[0][0] if last_update_res and last_update_res[0][0] else None

    # B. KPIs (Dédupliqués)
    # On calcule la somme des streams en ne prenant que la ligne la plus récente pour chaque jour/chanson
    kpi_query = f"""
        SELECT
            COUNT(DISTINCT song),
            SUM(streams)
        FROM (
            SELECT DISTINCT ON (date, song) song, streams
            FROM s4a_song_timeline
            WHERE song NOT ILIKE %s
            {artist_frag}
            ORDER BY date, song, collected_at DESC
        ) sub
    """
    stats_res = db.fetch_query(kpi_query, (f"%{ARTIST_NAME_FILTER}%", *artist_params))
    songs_count = stats_res[0][0] or 0
    total_streams_individual = stats_res[0][1] or 0

    # ============================================================================
    # 2. AFFICHAGE DES MÉTRIQUES (3 COLONNES)
    # ============================================================================
    st.header("🎯 Métriques Globales")
    col1, col2, col3 = st.columns(3)
    
    col1.metric("🎵 Chansons Actives", f"{songs_count}")
    col2.metric("🎧 Cumul Streams (Titres)", f"{total_streams_individual:,}")
    
    # C. Affichage intelligent de la date
    if last_update:
        time_diff = datetime.now() - last_update
        hours_ago = int(time_diff.total_seconds() / 3600)
        
        # Calcul du petit texte "delta" (ex: -2h)
        if hours_ago < 1:
            delta_str = "À l'instant"
            delta_color = "normal"
        elif hours_ago < 24:
            delta_str = f"Il y a {hours_ago}h"
            delta_color = "off"
        else:
            days = int(hours_ago / 24)
            delta_str = f"Il y a {days}j"
            delta_color = "off"

        col3.metric(
            "🕐 Dernière MàJ", 
            last_update.strftime('%d/%m %H:%M'), 
            delta=delta_str,
            delta_color=delta_color
        )
    else:
        col3.metric("🕐 Dernière MàJ", "Aucune donnée")
    
    st.markdown("---")
    
    # ============================================================================
    # 3. TOP CHANSONS (Dédupliqué)
    # ============================================================================
    st.header("🏆 Top Chansons")
    
    df_top = db.fetch_df(f"""
        SELECT
            song,
            SUM(streams) as total_streams
        FROM (
            SELECT DISTINCT ON (date, song) song, streams
            FROM s4a_song_timeline
            WHERE song NOT ILIKE %s
            {artist_frag}
            ORDER BY date, song, collected_at DESC
        ) sub
        GROUP BY song
        ORDER BY total_streams DESC
        LIMIT 10
    """, (f"%{ARTIST_NAME_FILTER}%", *artist_params))
    
    if not df_top.empty:
        fig_top = px.bar(
            df_top,
            x='total_streams',
            y='song',
            orientation='h',
            text='total_streams',
            labels={'total_streams': 'Streams', 'song': ''},
            color='total_streams',
            color_continuous_scale='viridis'
        )
        fig_top.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
        fig_top.update_layout(
            height=500,
            showlegend=False,
            xaxis_title="Total Streams",
            yaxis={'categoryorder':'total ascending'}
        )
        st.plotly_chart(fig_top, use_container_width=True)
    else:
        st.info("Pas de données disponibles.")
    
    st.markdown("---")
    
    # ============================================================================
    # 4. ÉVOLUTION DE L'AUDIENCE GLOBALE (Dédupliqué)
    # ============================================================================
    st.header("📈 Évolution de l'Audience Globale")
    st.caption("Calculé : Somme des streams dédupliqués jour par jour")
    
    col1, col2 = st.columns(2)
    default_start = datetime.now().date() - timedelta(days=365)
    start_date_aud = col1.date_input("Début", value=default_start, key="date_aud_start")
    end_date_aud = col2.date_input("Fin", value=datetime.now().date(), key="date_aud_end")
    
    audience_query = f"""
        SELECT date, SUM(streams) as daily_streams
        FROM (
            SELECT DISTINCT ON (date, song) date, streams
            FROM s4a_song_timeline
            WHERE song NOT ILIKE %s
            {artist_frag}
              AND date >= %s
              AND date <= %s
            ORDER BY date, song, collected_at DESC
        ) sub
        GROUP BY date
        ORDER BY date
    """
    df_audience = db.fetch_df(audience_query, (f"%{ARTIST_NAME_FILTER}%", *artist_params, start_date_aud, end_date_aud))
    
    if not df_audience.empty:
        fig_aud = go.Figure()
        
        fig_aud.add_trace(go.Scatter(
            x=df_audience['date'], 
            y=df_audience['daily_streams'], 
            name='Streams Totaux',
            mode='lines',
            fill='tozeroy',
            line=dict(color='#1DB954', width=3)
        ))
        
        fig_aud.update_layout(
            height=400, 
            hovermode='x unified',
            yaxis_title="Streams / Jour"
        )
        st.plotly_chart(fig_aud, use_container_width=True)
    else:
        st.info("Pas de données pour cette période.")

    # ============================================================================
    # 5. DÉTAIL PAR CHANSON
    # ============================================================================
    st.markdown("---")
    st.header("🎸 Détail par Chanson")
    
    songs_list = db.fetch_df(f"""
        SELECT song, MIN(date) AS first_seen
        FROM s4a_song_timeline
        WHERE song NOT ILIKE %s
        {artist_frag}
        GROUP BY song
        ORDER BY first_seen DESC
    """, (f"%{ARTIST_NAME_FILTER}%", *artist_params))
    
    if not songs_list.empty:
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            selected_song = st.selectbox("Sélectionner une chanson", songs_list['song'])
        
        with col2:
            start_date_song = st.date_input(
                "Début", 
                value=datetime.now().date() - timedelta(days=365),
                key="song_start"
            )
        with col3:
            end_date_song = st.date_input(
                "Fin", 
                value=datetime.now().date(),
                key="song_end"
            )
        
        # Même logique de déduplication ici aussi pour être cohérent
        df_song = db.fetch_df(f"""
            SELECT DISTINCT ON (date) date, streams
            FROM s4a_song_timeline
            WHERE song = %s
            {artist_frag}
              AND date >= %s AND date <= %s
            ORDER BY date, collected_at DESC
        """, (selected_song, *artist_params, start_date_song, end_date_song))
        
        if not df_song.empty:
            fig_song = px.line(
                df_song, 
                x='date', 
                y='streams', 
                title=f"Évolution Streams : {selected_song}", 
                markers=False 
            )
            fig_song.update_traces(line_color='#1DB954', line_width=2)
            st.plotly_chart(fig_song, use_container_width=True)
        else:
            st.info("Pas de données pour cette période.")
            
    db.close()

if __name__ == "__main__":
    show()