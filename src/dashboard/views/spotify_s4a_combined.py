"""Page Spotify & S4A - Vue consolidée et nettoyée."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from src.dashboard.utils import get_db_connection

# ⚠️ IMPORTANT : Le nom exact tel qu'il apparaît dans tes CSV pour la ligne "Total"
ARTIST_NAME_FILTER = "1x7xxxxxxx" 

def show():
    """Affiche la page Spotify & S4A combinée."""
    st.title("🎵 Spotify & S4A")
    st.markdown("### Analyse des performances (Source : Timeline CSV)")
    st.markdown("---")
    
    db = get_db_connection()
    
    # ============================================================================
    # 1. RÉCUPÉRATION DES DONNÉES GLOBALES
    # ============================================================================
    
    # A. Date de mise à jour
    update_query = "SELECT MAX(collected_at) FROM s4a_song_timeline"
    last_update_res = db.fetch_query(update_query)
    last_update = last_update_res[0][0] if last_update_res and last_update_res[0][0] else None

    # B. KPIs (Excluant l'artiste pour ne pas doubler)
    stats_query = """
        SELECT 
            COUNT(DISTINCT song), 
            SUM(streams)
        FROM s4a_song_timeline
        WHERE song NOT ILIKE %s
    """
    stats_res = db.fetch_query(stats_query, (f"%{ARTIST_NAME_FILTER}%",))
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
            delta_color = "off" # Gris
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
    # 3. TOP CHANSONS (Exclut l'artiste)
    # ============================================================================
    st.header("🏆 Top Chansons")
    
    df_top = db.fetch_df("""
        SELECT 
            song, 
            SUM(streams) as total_streams
        FROM s4a_song_timeline
        WHERE song NOT ILIKE %s
        GROUP BY song
        ORDER BY total_streams DESC
        LIMIT 10
    """, (f"%{ARTIST_NAME_FILTER}%",))
    
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
        st.plotly_chart(fig_top, width='stretch')
    else:
        st.info("Pas de données disponibles.")
    
    st.markdown("---")
    
    # ============================================================================
    # 4. ÉVOLUTION DE L'AUDIENCE GLOBALE (Calculée)
    # ============================================================================
    st.header("📈 Évolution de l'Audience Globale")
    st.caption("Calculé : Somme des streams de tous les titres par jour")
    
    # Filtres date
    col1, col2 = st.columns(2)
    default_start = datetime.now().date() - timedelta(days=365)
    start_date_aud = col1.date_input("Début", value=default_start, key="date_aud_start")
    end_date_aud = col2.date_input("Fin", value=datetime.now().date(), key="date_aud_end")
    
    # REQUÊTE : On somme tous les streams jour par jour
    audience_query = """
        SELECT date, SUM(streams) as daily_streams
        FROM s4a_song_timeline
        WHERE song NOT ILIKE %s 
          AND date >= %s 
          AND date <= %s
        GROUP BY date
        ORDER BY date
    """
    df_audience = db.fetch_df(audience_query, (f"%{ARTIST_NAME_FILTER}%", start_date_aud, end_date_aud))
    
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
        st.plotly_chart(fig_aud, width='stretch')
    else:
        st.info("Pas de données pour cette période.")

    # ============================================================================
    # 5. DÉTAIL PAR CHANSON (Filtre 365 jours par défaut)
    # ============================================================================
    st.markdown("---")
    st.header("🎸 Détail par Chanson")
    
    # Liste des chansons (SANS l'artiste)
    songs_list = db.fetch_df("""
        SELECT DISTINCT song 
        FROM s4a_song_timeline 
        WHERE song NOT ILIKE %s 
        ORDER BY song
    """, (f"%{ARTIST_NAME_FILTER}%",))
    
    if not songs_list.empty:
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            selected_song = st.selectbox("Sélectionner une chanson", songs_list['song'])
        
        with col2:
            # Filtre par défaut sur 365 jours
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
        
        df_song = db.fetch_df("""
            SELECT date, streams 
            FROM s4a_song_timeline 
            WHERE song = %s AND date >= %s AND date <= %s
            ORDER BY date
        """, (selected_song, start_date_song, end_date_song))
        
        if not df_song.empty:
            fig_song = px.line(
                df_song, 
                x='date', 
                y='streams', 
                title=f"Évolution Streams : {selected_song}", 
                markers=False 
            )
            fig_song.update_traces(line_color='#1DB954', line_width=2)
            st.plotly_chart(fig_song, width='stretch')
        else:
            st.info("Pas de données pour cette période.")
            
    db.close()

if __name__ == "__main__":
    show()