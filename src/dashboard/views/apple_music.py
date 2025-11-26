"""Vue Streamlit pour Apple Music."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from src.dashboard.utils import get_db_connection

def show():
    """Affiche la vue Apple Music."""
    st.title("🍎 Apple Music Analytics")
    st.markdown("### Analyse des performances et croissance quotidienne")
    st.markdown("---")
    
    db = get_db_connection()
    
    try:
        # ============================================================
        # 1. KPIs GLOBAUX
        # ============================================================
        st.subheader("📊 Vue d'ensemble")
        
        col1, col2, col3 = st.columns(3)
        
        # Total des chansons
        songs_count = db.get_table_count('apple_songs_performance')
        col1.metric("🎵 Chansons Suivies", f"{songs_count:,}")
        
        # Total Shazams et Plays (Dernier état connu)
        totals_query = """
            SELECT 
                COALESCE(SUM(plays), 0) as total_plays,
                COALESCE(SUM(shazam_count), 0) as total_shazams
            FROM apple_songs_performance
        """
        result = db.fetch_query(totals_query)
        total_plays, total_shazams = result[0] if result else (0, 0)
        
        col2.metric("▶️ Total Streams (Cumul)", f"{total_plays:,}")
        col3.metric("⚡ Total Shazams (Cumul)", f"{total_shazams:,}")
        
        st.markdown("---")
        
        # ============================================================
        # 2. TOP CHANSONS (Barres)
        # ============================================================
        st.subheader("🏆 Top Chansons (Cumulé)")
        
        top_query = """
            SELECT song_name, plays, shazam_count
            FROM apple_songs_performance
            ORDER BY plays DESC
            LIMIT 10
        """
        df_top = db.fetch_df(top_query)
        
        if not df_top.empty:
            fig = px.bar(
                df_top,
                x='plays',
                y='song_name',
                orientation='h',
                text='plays',
                title="Top 10 par Streams",
                labels={'plays': 'Streams', 'song_name': ''},
                color='plays',
                color_continuous_scale='Reds'
            )
            fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
            fig.update_layout(yaxis={'categoryorder':'total ascending'}, height=500)
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # ============================================================
        # 3. GRAPHIQUE DYNAMIQUE (CALCUL DIFFÉRENTIEL)
        # ============================================================
        st.subheader("📈 Croissance Quotidienne (Streams & Shazams)")
        
        # Récupérer la liste des chansons pour le filtre
        songs_list = db.fetch_df("SELECT DISTINCT song_name FROM apple_songs_history ORDER BY song_name")
        
        if not songs_list.empty:
            # Filtre dynamique
            selected_songs = st.multiselect(
                "🔍 Filtrer par chanson(s)",
                options=songs_list['song_name'].tolist(),
                default=songs_list['song_name'].tolist()[:3]  # 3 premiers par défaut
            )
            
            if selected_songs:
                # ⚠️ LA MAGIE EST ICI : Requête SQL avec LAG() pour calculer la différence
                # On calcule : Valeur Aujourd'hui - Valeur Hier
                placeholders = ','.join(['%s'] * len(selected_songs))
                
                daily_calc_query = f"""
                    WITH daily_diff AS (
                        SELECT 
                            date,
                            song_name,
                            plays,
                            shazam_count,
                            plays - LAG(plays) OVER (PARTITION BY song_name ORDER BY date) as daily_streams,
                            shazam_count - LAG(shazam_count) OVER (PARTITION BY song_name ORDER BY date) as daily_shazams
                        FROM apple_songs_history
                        WHERE song_name IN ({placeholders})
                    )
                    SELECT * FROM daily_diff 
                    WHERE daily_streams IS NOT NULL -- On enlève le premier jour qui n'a pas de précédent
                    AND date >= CURRENT_DATE - INTERVAL '30 days'
                    ORDER BY date
                """
                
                df_daily = db.fetch_df(daily_calc_query, tuple(selected_songs))
                
                if not df_daily.empty:
                    # Nettoyage des valeurs négatives (si Apple corrige ses chiffres à la baisse)
                    df_daily['daily_streams'] = df_daily['daily_streams'].apply(lambda x: max(0, x))
                    df_daily['daily_shazams'] = df_daily['daily_shazams'].apply(lambda x: max(0, x))
                    
                    tab1, tab2 = st.tabs(["🎧 Streams / Jour", "⚡ Shazams / Jour"])
                    
                    with tab1:
                        fig_streams = px.line(
                            df_daily, x='date', y='daily_streams', color='song_name',
                            title="Nouveaux Streams par Jour", markers=True
                        )
                        fig_streams.update_layout(hovermode='x unified')
                        st.plotly_chart(fig_streams, use_container_width=True)
                        
                    with tab2:
                        fig_shazams = px.bar(
                            df_daily, x='date', y='daily_shazams', color='song_name',
                            title="Nouveaux Shazams par Jour", barmode='group'
                        )
                        fig_shazams.update_layout(hovermode='x unified')
                        st.plotly_chart(fig_shazams, use_container_width=True)
                        
                else:
                    st.info("📉 Pas assez d'historique pour calculer la croissance (besoin de min. 2 jours de données).")
            else:
                st.info("👈 Sélectionnez des chansons.")
        else:
            st.warning("⚠️ L'historique est vide. Importez des CSV plusieurs jours de suite pour voir les courbes.")

    except Exception as e:
        st.error(f"❌ Erreur : {e}")
    
    finally:
        db.close()

if __name__ == "__main__":
    show()