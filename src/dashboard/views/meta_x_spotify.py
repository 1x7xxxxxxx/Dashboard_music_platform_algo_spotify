"""Page META x SPOTIFY - Corrélation des performances."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
import sys
from datetime import datetime, timedelta

from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader

from dashboard.utils import get_db_connection

def get_available_songs():
    """Récupère la liste des chansons avec mapping actif."""
    db = get_db()
    
    query = """
        SELECT DISTINCT
            m.song,
            COUNT(DISTINCT m.campaign_id) as campaigns_count,
            MAX(t.popularity) as max_popularity,
            MAX(sg.streams) as total_streams
        FROM meta_spotify_mapping m
        LEFT JOIN tracks t ON m.track_id = t.track_id
        LEFT JOIN s4a_songs_global sg ON m.song = sg.song
        WHERE m.is_active = true
        GROUP BY m.song
        ORDER BY total_streams DESC NULLS LAST
    """
    
    df = db.fetch_df(query)
    db.close()
    
    return df


def get_combined_data(song: str, start_date, end_date):
    """
    Récupère les données combinées META + SPOTIFY pour une chanson.
    
    Returns:
        DataFrame avec : date, streams, popularity, conversions
    """
    db = get_db()
    
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
        
        -- Conversions quotidiennes depuis Meta (agrégées si plusieurs campagnes)
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
    
    # ============================================================================
    # VÉRIFIER SI LA TABLE DE MAPPING EXISTE
    # ============================================================================
    mapping_exists_query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'meta_spotify_mapping'
        )
    """
    
    mapping_exists = db.fetch_query(mapping_exists_query)[0][0]
    
    if not mapping_exists:
        st.error("❌ Table de mapping non trouvée")
        st.info("""
        **Pour utiliser cette page, vous devez d'abord créer la table de mapping :**
        
        ```bash
        python create_mapping_table.py
        python manage_mapping.py
        ```
        """)
        db.close()
        return
    
    # ============================================================================
    # RÉCUPÉRER LES CHANSONS AVEC MAPPING
    # ============================================================================
    df_songs = get_available_songs()
    
    if df_songs.empty:
        st.warning("⚠️ Aucun mapping campagne ↔ chanson trouvé")
        st.info("""
        **Pour lier vos campagnes Meta à vos chansons Spotify :**
        
        ```bash
        python manage_mapping.py
        ```
        
        Ce script vous permettra de :
        - Lister vos campagnes Meta
        - Lister vos chansons Spotify
        - Créer des liens entre campagnes et chansons
        """)
        db.close()
        return
    
    # ============================================================================
    # FILTRES
    # ============================================================================
    st.header("🔍 Filtres")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        # Dropdown des chansons
        song_options = df_songs['song'].tolist()
        
        selected_song = st.selectbox(
            "🎵 Sélectionner une chanson",
            options=song_options,
            key="song_selector"
        )
    
    with col2:
        # Date début
        start_date = st.date_input(
            "📅 Date début",
            value=datetime.now().date() - timedelta(days=30),
            format="DD/MM/YYYY",
            key="start_date_meta_spotify"
        )
    
    with col3:
        # Date fin
        end_date = st.date_input(
            "📅 Date fin",
            value=datetime.now().date(),
            format="DD/MM/YYYY",
            key="end_date_meta_spotify"
        )
    
    st.markdown("---")
    
    # ============================================================================
    # INFORMATIONS SUR LA CHANSON SÉLECTIONNÉE
    # ============================================================================
    selected_song_info = df_songs[df_songs['song'] == selected_song].iloc[0]
    
    col1, col2, col3 = st.columns(3)
    
    col1.metric(
        "🎯 Campagnes Liées",
        f"{int(selected_song_info['campaigns_count'])}"
    )
    
    col2.metric(
        "📊 Popularité Spotify",
        f"{int(selected_song_info['max_popularity']) if pd.notna(selected_song_info['max_popularity']) else 'N/A'}/100"
    )
    
    col3.metric(
        "🎧 Streams Totaux",
        f"{int(selected_song_info['total_streams']):,}" if pd.notna(selected_song_info['total_streams']) else "N/A"
    )
    
    st.markdown("---")
    
    # ============================================================================
    # RÉCUPÉRER LES DONNÉES COMBINÉES
    # ============================================================================
    df_data = get_combined_data(selected_song, start_date, end_date)
    
    if df_data.empty:
        st.warning(f"⚠️ Aucune donnée disponible pour '{selected_song}' sur cette période")
        db.close()
        return
    
    # Convertir la colonne date
    df_data['date'] = pd.to_datetime(df_data['date'])
    
    # ============================================================================
    # GRAPHIQUE COMBINÉ
    # ============================================================================
    st.header("📈 Performance Croisée")
    
    # Créer le graphique
    fig = go.Figure()
    
    # 1. BARRES : Streams quotidiens (Aire remplie)
    fig.add_trace(go.Scatter(
        x=df_data['date'],
        y=df_data['streams'],
        name='Streams',
        mode='lines',
        fill='tozeroy',
        fillcolor='rgba(29, 185, 84, 0.3)',
        line=dict(color='#1DB954', width=2),
        yaxis='y',
        hovertemplate='<b>Streams</b><br>%{y:,.0f}<extra></extra>'
    ))
    
    # 2. LIGNE : Popularité Spotify (constante sur la période)
    fig.add_trace(go.Scatter(
        x=df_data['date'],
        y=df_data['popularity'],
        name='Popularité Spotify',
        mode='lines',
        line=dict(color='#FF9500', width=3, dash='dot'),
        yaxis='y2',
        hovertemplate='<b>Popularité</b><br>%{y}/100<extra></extra>'
    ))
    
    # 3. LIGNE : Conversions Meta
    fig.add_trace(go.Scatter(
        x=df_data['date'],
        y=df_data['conversions'],
        name='Conversions Meta',
        mode='lines+markers',
        line=dict(color='#FF3B30', width=2),
        marker=dict(size=6, symbol='circle'),
        yaxis='y3',
        hovertemplate='<b>Conversions</b><br>%{y:,.0f}<extra></extra>'
    ))
    
    # Configuration des axes
    fig.update_layout(
        title=f"Performance : {selected_song}",
        xaxis=dict(
            title='Date',
            tickformat='%d/%m/%Y',
            showgrid=True
        ),
        yaxis=dict(
            title='Streams',
            side='left',
            showgrid=True,
            rangemode='tozero'
        ),
        yaxis2=dict(
            title='Popularité (0-100)',
            side='right',
            overlaying='y',
            showgrid=False,
            range=[0, 100]
        ),
        yaxis3=dict(
            title='Conversions',
            side='right',
            overlaying='y',
            anchor='free',
            position=0.95,
            showgrid=False,
            rangemode='tozero'
        ),
        height=600,
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # ============================================================================
    # STATISTIQUES DE LA PÉRIODE
    # ============================================================================
    st.header("📊 Statistiques de la période")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_streams = df_data['streams'].sum()
    col1.metric(
        "🎧 Streams Totaux",
        f"{total_streams:,.0f}"
    )
    
    avg_daily_streams = df_data['streams'].mean()
    col2.metric(
        "📊 Moy. Streams/jour",
        f"{avg_daily_streams:,.0f}"
    )
    
    total_conversions = df_data['conversions'].sum()
    col3.metric(
        "🎯 Conversions Totales",
        f"{int(total_conversions):,}"
    )
    
    avg_popularity = df_data['popularity'].iloc[0] if not df_data.empty else 0
    col4.metric(
        "📈 Popularité Spotify",
        f"{int(avg_popularity)}/100"
    )
    
    st.markdown("---")
    
    # ============================================================================
    # ANALYSE DE CORRÉLATION
    # ============================================================================
    st.header("🔬 Analyse de Corrélation")
    
    # Calculer les corrélations
    if df_data['conversions'].sum() > 0 and df_data['streams'].sum() > 0:
        # Filtrer les jours où il y a des conversions ET des streams
        df_corr = df_data[(df_data['conversions'] > 0) & (df_data['streams'] > 0)].copy()
        
        if len(df_corr) > 2:
            corr_conv_streams = df_corr[['conversions', 'streams']].corr().iloc[0, 1]
            
            col1, col2, col3 = st.columns(3)
            
            col1.metric(
                "📈 Corrélation Conversions ↔ Streams",
                f"{corr_conv_streams:.2f}",
                help="Coefficient de corrélation de Pearson (-1 à 1)"
            )
            
            # Interprétation
            if corr_conv_streams > 0.7:
                interpretation = "🟢 Forte corrélation positive"
                desc = "Les conversions Meta semblent stimuler les streams Spotify"
            elif corr_conv_streams > 0.3:
                interpretation = "🟡 Corrélation positive modérée"
                desc = "Impact modéré des conversions sur les streams"
            elif corr_conv_streams > -0.3:
                interpretation = "⚪ Corrélation faible"
                desc = "Pas de lien clair entre conversions et streams"
            else:
                interpretation = "🔴 Corrélation négative"
                desc = "Les conversions ne semblent pas impacter les streams"
            
            col2.metric(
                "🎯 Interprétation",
                interpretation
            )
            
            col3.info(desc)
        else:
            st.info("ℹ️ Pas assez de données pour calculer une corrélation significative")
    else:
        st.info("ℹ️ Pas de conversions ou streams sur cette période")
    
    st.markdown("---")
    
    # ============================================================================
    # TABLEAU DÉTAILLÉ
    # ============================================================================
    with st.expander("📋 Voir les données détaillées"):
        df_display = df_data.copy()
        df_display['date'] = df_display['date'].dt.strftime('%d/%m/%Y')
        
        st.dataframe(
            df_display,
            hide_index=True,
            use_container_width=True,
            column_config={
                'date': 'Date',
                'streams': st.column_config.NumberColumn('Streams', format='%d'),
                'popularity': st.column_config.NumberColumn('Popularité', format='%d/100'),
                'conversions': st.column_config.NumberColumn('Conversions', format='%d')
            }
        )
    
    # ============================================================================
    # CAMPAGNES LIÉES
    # ============================================================================
    st.markdown("---")
    st.header("📱 Campagnes Meta Liées")
    
    campaigns_query = """
        SELECT 
            c.campaign_name,
            c.status,
            COALESCE(SUM(i.conversions), 0) as total_conversions,
            ROUND(COALESCE(SUM(i.spend), 0), 2) as total_spend,
            CASE 
                WHEN SUM(i.conversions) > 0 
                THEN ROUND(SUM(i.spend) / SUM(i.conversions), 2)
                ELSE NULL 
            END as cpr
        FROM meta_spotify_mapping m
        JOIN meta_campaigns c ON m.campaign_id = c.campaign_id
        LEFT JOIN meta_ads a ON c.campaign_id = a.campaign_id
        LEFT JOIN meta_insights i ON a.ad_id = i.ad_id 
            AND i.date >= %s 
            AND i.date <= %s
        WHERE m.song = %s AND m.is_active = true
        GROUP BY c.campaign_id, c.campaign_name, c.status
        ORDER BY total_conversions DESC
    """
    
    df_campaigns = db.fetch_df(campaigns_query, (start_date, end_date, selected_song))
    
    if not df_campaigns.empty:
        # Formater pour affichage
        df_campaigns_display = df_campaigns.copy()
        df_campaigns_display['total_conversions'] = df_campaigns_display['total_conversions'].apply(
            lambda x: f"{int(x):,}"
        )
        df_campaigns_display['total_spend'] = df_campaigns_display['total_spend'].apply(
            lambda x: f"{x:,.2f} €"
        )
        df_campaigns_display['cpr'] = df_campaigns_display['cpr'].apply(
            lambda x: f"{x:.2f} €" if pd.notna(x) else "N/A"
        )
        
        df_campaigns_display = df_campaigns_display.rename(columns={
            'campaign_name': 'Nom Campagne',
            'status': 'Statut',
            'total_conversions': 'Conversions',
            'total_spend': 'Dépenses',
            'cpr': 'CPR'
        })
        
        st.dataframe(
            df_campaigns_display,
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("ℹ️ Aucune campagne active sur cette période")
    
    # Footer
    st.markdown("---")
    st.caption(f"📊 Dernière mise à jour : {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    db.close()


if __name__ == "__main__":
    show()