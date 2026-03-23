"""Vue Streamlit pour YouTube (Optimisée Dark Mode & Multi-Axes)."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import isodate
from datetime import datetime
from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id

def parse_duration(duration_str):
    """Convertit 'PT1M30S' en secondes."""
    try:
        if not duration_str: return 0
        td = isodate.parse_duration(duration_str)
        return td.total_seconds()
    except:
        return 0

def show():
    st.title("🎬 YouTube Analytics")
    st.markdown("### Analyse de la Chaîne et des Vidéos")
    st.markdown("---")
    
    db = get_db_connection()
    artist_id = get_artist_id() or 1

    try:
        # ============================================================================
        # 1. ANALYSE GLOBALE (CHAÎNE)
        # ============================================================================
        st.subheader("📈 Évolution de la Chaîne")
        
        hist_query = """
            SELECT date(collected_at) as date,
                   MAX(subscriber_count) as subs,
                   MAX(view_count) as views
            FROM youtube_channel_history
            WHERE artist_id = %s
            GROUP BY date(collected_at)
            ORDER BY date
        """
        df_hist = db.fetch_df(hist_query, (artist_id,))
        
        if not df_hist.empty:
            fig_channel = go.Figure()
            
            # Axe Y1 (Gauche) : Abonnés (Zone remplie Rouge)
            fig_channel.add_trace(go.Scatter(
                x=df_hist['date'], y=df_hist['subs'],
                name='Abonnés',
                mode='lines',
                fill='tozeroy',
                line=dict(color='#FF0000', width=2),
                yaxis='y'
            ))
            
            # Axe Y2 (Droite) : Vues Totales (Blanc/Gris clair pour Dark Mode)
            # ✅ CORRECTION COULEUR (Visible sur fond noir)
            fig_channel.add_trace(go.Scatter(
                x=df_hist['date'], y=df_hist['views'],
                name='Vues Totales',
                mode='lines+markers',
                line=dict(color='#E0E0E0', width=2, dash='dot'), 
                yaxis='y2'
            ))
            
            fig_channel.update_layout(
                title="Croissance : Abonnés vs Vues Totales",
                xaxis=dict(title="Date"),
                yaxis=dict(
                    title="Abonnés", 
                    titlefont=dict(color="#FF0000"),
                    tickfont=dict(color="#FF0000")
                ),
                yaxis2=dict(
                    title="Vues Cumulées",
                    titlefont=dict(color="#E0E0E0"),
                    tickfont=dict(color="#E0E0E0"),
                    overlaying='y',
                    side='right',
                    showgrid=False
                ),
                hovermode='x unified',
                legend=dict(orientation="h", y=1.1),
                height=450
            )
            st.plotly_chart(fig_channel, width='stretch')
            
            # KPIs actuels
            latest = df_hist.iloc[-1]
            c1, c2 = st.columns(2)
            c1.metric("👥 Abonnés Actuels", f"{int(latest['subs']):,}")
            c2.metric("👁️ Vues Totales", f"{int(latest['views']):,}")
            
        else:
            st.info("Pas encore d'historique pour la chaîne.")

        st.markdown("---")

        # ============================================================================
        # 2. ANALYSE VIDÉOS (TOP & SHORTS)
        # ============================================================================
        
        # Récupération des vidéos + stats
        videos_query = """
            SELECT
                v.title, v.duration, v.published_at, v.thumbnail_url,
                vs.view_count, vs.like_count, vs.comment_count
            FROM youtube_videos v
            JOIN (
                SELECT video_id, MAX(collected_at) as max_date
                FROM youtube_video_stats
                WHERE artist_id = %s
                GROUP BY video_id
            ) latest ON v.video_id = latest.video_id
            JOIN youtube_video_stats vs ON vs.video_id = latest.video_id AND vs.collected_at = latest.max_date
            WHERE v.artist_id = %s
            ORDER BY vs.view_count DESC
        """
        df_videos = db.fetch_df(videos_query, (artist_id, artist_id))
        
        if not df_videos.empty:
            # Traitement
            df_videos['seconds'] = df_videos['duration'].apply(parse_duration)
            df_videos['type'] = df_videos['seconds'].apply(lambda x: 'Short 📱' if 0 < x <= 60 else 'Vidéo 📹')
            
            # Calcul Ratio Vues/Like (Combien de vues pour 1 like ?)
            df_videos['ratio_views_like'] = df_videos.apply(
                lambda x: x['view_count'] / x['like_count'] if x['like_count'] > 0 else 0, axis=1
            )
            
            # Filtres
            st.subheader("🏆 Top Contenus (Analyse Multi-Axes)")
            
            c_filter1, c_filter2 = st.columns(2)
            with c_filter1:
                selected_type = st.selectbox("Type de contenu", ["Tous", "Vidéo 📹", "Short 📱"])
            
            with c_filter2:
                top_n = st.slider("Nombre de vidéos", 5, 50, 10)

            # Application filtres
            df_filtered = df_videos.copy()
            if selected_type != "Tous":
                df_filtered = df_filtered[df_filtered['type'] == selected_type]
            
            df_top = df_filtered.head(top_n)
            
            if not df_top.empty:
                # GRAPHIQUE 4 AXES (Vues, Likes, Coms, Ratio)
                fig_top = go.Figure()
                
                # 1. Vues (Barres - Axe Gauche)
                fig_top.add_trace(go.Bar(
                    x=df_top['title'], 
                    y=df_top['view_count'],
                    name='Vues',
                    marker_color='#FF0000', # Rouge
                    yaxis='y'
                ))
                
                # 2. Likes (Ligne - Axe Droit 1)
                fig_top.add_trace(go.Scatter(
                    x=df_top['title'], 
                    y=df_top['like_count'],
                    name='Likes',
                    mode='lines+markers',
                    line=dict(color='#2ECC71', width=3), # Vert
                    yaxis='y2'
                ))

                # 3. Commentaires (Ligne - Axe Droit 2 - Décalé)
                fig_top.add_trace(go.Scatter(
                    x=df_top['title'], 
                    y=df_top['comment_count'],
                    name='Commentaires',
                    mode='lines+markers',
                    line=dict(color='#9B59B6', width=2), # Violet
                    yaxis='y3'
                ))

                # 4. Ratio Vues/Like (Ligne - Axe Droit 3 - Décalé)
                # Note : Plus c'est bas, meilleur c'est
                fig_top.add_trace(go.Scatter(
                    x=df_top['title'], 
                    y=df_top['ratio_views_like'],
                    name='Ratio Vues/Like',
                    mode='lines',
                    line=dict(color='#F1C40F', width=2, dash='dot'), # Jaune
                    yaxis='y4'
                ))
                
                fig_top.update_layout(
                    title=f"Top {top_n} {selected_type}",
                    xaxis=dict(title="", tickangle=45),
                    
                    # Axe 1 : Vues (Gauche)
                    yaxis=dict(
                        title="Vues", 
                        titlefont=dict(color="#FF0000"),
                        tickfont=dict(color="#FF0000"),
                        side='left',
                        showgrid=True
                    ),
                    
                    # Axe 2 : Likes (Droite)
                    yaxis2=dict(
                        title="Likes",
                        titlefont=dict(color="#2ECC71"),
                        tickfont=dict(color="#2ECC71"),
                        side='right',
                        overlaying='y',
                        showgrid=False
                    ),
                    
                    # Axe 3 : Commentaires (Droite décalée)
                    yaxis3=dict(
                        title="Coms",
                        titlefont=dict(color="#9B59B6"),
                        tickfont=dict(color="#9B59B6"),
                        anchor="free",
                        overlaying='y',
                        side='right',
                        position=0.94, # Décalage vers la gauche
                        showgrid=False
                    ),

                    # Axe 4 : Ratio (Droite décalée)
                    yaxis4=dict(
                        title="Ratio V/L",
                        titlefont=dict(color="#F1C40F"),
                        tickfont=dict(color="#F1C40F"),
                        anchor="free",
                        overlaying='y',
                        side='right',
                        position=0.88, # Décalage encore plus à gauche
                        showgrid=False
                    ),

                    hovermode='x unified',
                    # Légende en haut pour ne pas gêner
                    legend=dict(orientation="h", y=1.15, x=0.5, xanchor='center'),
                    height=650,
                    margin=dict(b=100, r=50) # Marges pour les axes multiples
                )
                
                st.plotly_chart(fig_top, width='stretch')
                
            else:
                st.info("Aucune vidéo dans cette catégorie.")
        else:
            st.warning("Aucune vidéo trouvée en base.")

    except Exception as e:
        st.error(f"Erreur : {e}")
    finally:
        db.close()

if __name__ == "__main__":
    show()