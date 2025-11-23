"""Vue Streamlit pour YouTube - VERSION CORRIGÉE."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
from pathlib import Path

from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader

from dashboard.utils import get_db_connection

def show():
    """Affiche la vue YouTube."""
    st.title("🎬 YouTube Analytics")
    st.markdown("---")
    
    db = get_db_connection()
    
    try:
        # ============================================================
        # KPIs CHAÎNE
        # ============================================================
        st.subheader("📊 Vue d'ensemble de la chaîne")
        
        # Stats actuelles de la chaîne
        channel_query = """
            SELECT 
                channel_name,
                subscriber_count,
                video_count,
                view_count,
                collected_at
            FROM youtube_channels
            ORDER BY collected_at DESC
            LIMIT 1
        """
        
        channel_result = db.fetch_query(channel_query)
        
        if channel_result and channel_result[0]:
            channel_name, subs, videos, views, collected_at = channel_result[0]
            
            col1, col2, col3, col4 = st.columns(4)
            
            col1.metric("👥 Abonnés", f"{subs:,}")
            col2.metric("📹 Vidéos", f"{videos:,}")
            col3.metric("👁️ Vues totales", f"{views:,}")
            
            # Dernière collecte
            time_diff = datetime.now() - collected_at
            hours_ago = int(time_diff.total_seconds() / 3600)
            
            if hours_ago < 1:
                col4.metric("🕐 Dernière collecte", "< 1h")
            elif hours_ago < 24:
                col4.metric("🕐 Dernière collecte", f"Il y a {hours_ago}h")
            else:
                days_ago = int(hours_ago / 24)
                col4.metric("🕐 Dernière collecte", f"Il y a {days_ago}j")
        else:
            st.info("📭 Aucune donnée de chaîne. Lancez la collecte YouTube.")
        
        st.markdown("---")
        
        # ============================================================
        # ÉVOLUTION DE LA CHAÎNE
        # ============================================================
        history_count = db.get_table_count('youtube_channel_history')
        
        if history_count > 1:
            st.subheader("📈 Évolution de la chaîne")
            
            history_query = """
                SELECT 
                    collected_at::date as date,
                    MAX(subscriber_count) as subscribers,
                    MAX(view_count) as views
                FROM youtube_channel_history
                GROUP BY collected_at::date
                ORDER BY date
            """
            
            df_history = db.fetch_df(history_query)
            
            if not df_history.empty:
                tab1, tab2 = st.tabs(["📊 Abonnés", "👁️ Vues"])
                
                with tab1:
                    fig = px.line(
                        df_history,
                        x='date',
                        y='subscribers',
                        title='Évolution du nombre d\'abonnés',
                        markers=True
                    )
                    fig.update_traces(line_color='#FF0000')
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Croissance
                    if len(df_history) > 1:
                        growth = df_history['subscribers'].iloc[-1] - df_history['subscribers'].iloc[0]
                        col1, col2 = st.columns(2)
                        col1.metric("📈 Croissance totale", f"+{growth:,}")
                        
                        days = (df_history['date'].iloc[-1] - df_history['date'].iloc[0]).days
                        if days > 0:
                            avg_per_day = growth / days
                            col2.metric("📊 Moyenne par jour", f"+{avg_per_day:.1f}")
                
                with tab2:
                    fig = px.area(
                        df_history,
                        x='date',
                        y='views',
                        title='Évolution des vues totales',
                        color_discrete_sequence=['#FF0000']
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
        
        # ============================================================
        # TOP VIDÉOS
        # ============================================================
        st.subheader("🏆 Top Vidéos")
        
        top_videos_query = """
            SELECT 
                v.video_id,
                v.title,
                v.published_at,
                MAX(vs.view_count) as views,
                MAX(vs.like_count) as likes,
                MAX(vs.comment_count) as comments
            FROM youtube_videos v
            LEFT JOIN youtube_video_stats vs ON v.video_id = vs.video_id
            GROUP BY v.video_id, v.title, v.published_at
            ORDER BY views DESC
            LIMIT 10
        """
        
        df_top_videos = db.fetch_df(top_videos_query)
        
        if not df_top_videos.empty:
            tab1, tab2, tab3 = st.tabs(["📊 Par Vues", "👍 Par Likes", "📋 Tableau"])
            
            with tab1:
                fig = px.bar(
                    df_top_videos,
                    x='views',
                    y='title',
                    orientation='h',
                    title='Top 10 Vidéos par Nombre de Vues',
                    labels={'views': 'Vues', 'title': 'Vidéo'},
                    color='views',
                    color_continuous_scale='Reds'
                )
                fig.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig, use_container_width=True)
            
            with tab2:
                fig = px.bar(
                    df_top_videos,
                    x='likes',
                    y='title',
                    orientation='h',
                    title='Top 10 Vidéos par Nombre de Likes',
                    labels={'likes': 'Likes', 'title': 'Vidéo'},
                    color='likes',
                    color_continuous_scale='Blues'
                )
                fig.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig, use_container_width=True)
            
            with tab3:
                # Calculer engagement rate
                df_top_videos['engagement'] = ((df_top_videos['likes'] + df_top_videos['comments']) / df_top_videos['views'] * 100).round(2)
                
                # Formater pour affichage
                df_display = df_top_videos[['title', 'views', 'likes', 'comments', 'engagement', 'published_at']].copy()
                df_display.columns = ['Titre', 'Vues', 'Likes', 'Commentaires', 'Engagement %', 'Publiée le']
                df_display['Publiée le'] = pd.to_datetime(df_display['Publiée le']).dt.strftime('%Y-%m-%d')
                
                st.dataframe(df_display, use_container_width=True, hide_index=True)
                
                # Export CSV
                csv = df_display.to_csv(index=False)
                st.download_button(
                    label="📥 Télécharger en CSV",
                    data=csv,
                    file_name=f"youtube_top_videos_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        else:
            st.info("📭 Aucune donnée de vidéos disponible")
        
        st.markdown("---")
        
        # ============================================================
        # PERFORMANCES VIDÉOS
        # ============================================================
        video_stats_count = db.get_table_count('youtube_video_stats')
        
        if video_stats_count > 0:
            st.subheader("📈 Performances des vidéos")
            
            # ✅ CORRECTION : Ajouter published_at dans SELECT pour ORDER BY
            videos_list_query = """
                SELECT DISTINCT 
                    v.video_id, 
                    v.title,
                    v.published_at
                FROM youtube_videos v
                INNER JOIN youtube_video_stats vs ON v.video_id = vs.video_id
                ORDER BY v.published_at DESC
                LIMIT 20
            """
            
            df_videos = db.fetch_df(videos_list_query)
            
            if not df_videos.empty:
                selected_video = st.selectbox(
                    "Sélectionnez une vidéo",
                    options=df_videos['video_id'].tolist(),
                    format_func=lambda x: df_videos[df_videos['video_id'] == x]['title'].values[0]
                )
                
                if selected_video:
                    # Historique de la vidéo
                    video_history_query = """
                        SELECT 
                            collected_at::date as date,
                            view_count,
                            like_count,
                            comment_count
                        FROM youtube_video_stats
                        WHERE video_id = %s
                        ORDER BY collected_at
                    """
                    
                    df_video_history = db.fetch_df(video_history_query, (selected_video,))
                    
                    if not df_video_history.empty and len(df_video_history) > 1:
                        fig = go.Figure()
                        
                        fig.add_trace(go.Scatter(
                            x=df_video_history['date'],
                            y=df_video_history['view_count'],
                            mode='lines+markers',
                            name='Vues',
                            line=dict(color='#FF0000')
                        ))
                        
                        fig.add_trace(go.Scatter(
                            x=df_video_history['date'],
                            y=df_video_history['like_count'],
                            mode='lines+markers',
                            name='Likes',
                            yaxis='y2',
                            line=dict(color='#0066FF')
                        ))
                        
                        fig.update_layout(
                            title='Évolution des Vues et Likes',
                            yaxis=dict(title='Vues'),
                            yaxis2=dict(title='Likes', overlaying='y', side='right'),
                            hovermode='x unified'
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("📊 Pas assez de données historiques pour cette vidéo")
            
            st.markdown("---")
        
        # ============================================================
        # PLAYLISTS
        # ============================================================
        playlists_count = db.get_table_count('youtube_playlists')
        
        if playlists_count > 0:
            st.subheader("📋 Playlists")
            
            playlists_query = """
                SELECT 
                    title,
                    video_count,
                    published_at
                FROM youtube_playlists
                ORDER BY video_count DESC
            """
            
            df_playlists = db.fetch_df(playlists_query)
            
            if not df_playlists.empty:
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    fig = px.bar(
                        df_playlists,
                        x='video_count',
                        y='title',
                        orientation='h',
                        title='Nombre de vidéos par playlist',
                        color='video_count',
                        color_continuous_scale='Oranges'
                    )
                    fig.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.metric("📋 Total playlists", len(df_playlists))
                    total_videos_in_playlists = df_playlists['video_count'].sum()
                    st.metric("📹 Total vidéos", total_videos_in_playlists)
            
            st.markdown("---")
        
        # ============================================================
        # COMMENTAIRES
        # ============================================================
        comments_count = db.get_table_count('youtube_comments')
        
        if comments_count > 0:
            st.subheader("💬 Engagement - Commentaires")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("💬 Total commentaires", f"{comments_count:,}")
            
            # Top commentateurs
            top_commenters_query = """
                SELECT 
                    author,
                    COUNT(*) as comment_count,
                    SUM(like_count) as total_likes
                FROM youtube_comments
                GROUP BY author
                ORDER BY comment_count DESC
                LIMIT 10
            """
            
            df_commenters = db.fetch_df(top_commenters_query)
            
            if not df_commenters.empty:
                with col2:
                    avg_likes = df_commenters['total_likes'].sum() / comments_count
                    st.metric("👍 Likes moyens/commentaire", f"{avg_likes:.1f}")
                
                st.markdown("##### Top 10 Commentateurs")
                fig = px.bar(
                    df_commenters,
                    x='comment_count',
                    y='author',
                    orientation='h',
                    title='Top Commentateurs',
                    color='total_likes',
                    color_continuous_scale='Greens'
                )
                fig.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig, use_container_width=True)
    
    except Exception as e:
        st.error(f"❌ Erreur lors du chargement des données : {e}")
        import traceback
        st.code(traceback.format_exc())
    
    finally:
        db.close()


if __name__ == "__main__":
    show()