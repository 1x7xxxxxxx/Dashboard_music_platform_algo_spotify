"""Vue Streamlit pour Apple Music."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

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
    """Affiche la vue Apple Music."""
    st.title("🍎 Apple Music Analytics")
    st.markdown("---")
    
    db = get_db()
    
    try:
        # ============================================================
        # KPIs GLOBAUX
        # ============================================================
        st.subheader("📊 Vue d'ensemble")
        
        col1, col2, col3, col4 = st.columns(4)
        
        # Total des chansons
        songs_count = db.get_table_count('apple_songs_performance')
        col1.metric("🎵 Chansons", f"{songs_count:,}")
        
        # Total plays
        total_plays_query = """
            SELECT COALESCE(SUM(plays), 0) as total_plays
            FROM apple_songs_performance
        """
        result = db.fetch_query(total_plays_query)
        total_plays = result[0][0] if result else 0
        col2.metric("▶️ Total Plays", f"{total_plays:,}")
        
        # Total listeners
        total_listeners_query = """
            SELECT COALESCE(SUM(listeners), 0) as total_listeners
            FROM apple_songs_performance
        """
        result = db.fetch_query(total_listeners_query)
        total_listeners = result[0][0] if result else 0
        col3.metric("👥 Total Listeners", f"{total_listeners:,}")
        
        # Dernière collecte
        last_update_query = """
            SELECT MAX(collected_at)
            FROM apple_songs_performance
        """
        result = db.fetch_query(last_update_query)
        if result and result[0][0]:
            last_update = result[0][0]
            time_diff = datetime.now() - last_update
            hours_ago = int(time_diff.total_seconds() / 3600)
            
            if hours_ago < 1:
                col4.metric("🕐 Dernière collecte", "< 1h")
            elif hours_ago < 24:
                col4.metric("🕐 Dernière collecte", f"Il y a {hours_ago}h")
            else:
                days_ago = int(hours_ago / 24)
                col4.metric("🕐 Dernière collecte", f"Il y a {days_ago}j")
        else:
            col4.metric("🕐 Dernière collecte", "Aucune")
        
        st.markdown("---")
        
        # ============================================================
        # TOP CHANSONS
        # ============================================================
        st.subheader("🏆 Top Chansons")
        
        tab1, tab2, tab3 = st.tabs(["📊 Par Plays", "👥 Par Listeners", "📈 Tableau détaillé"])
        
        with tab1:
            # Top 10 par plays
            top_plays_query = """
                SELECT 
                    song_name,
                    album_name,
                    plays,
                    listeners,
                    collected_at
                FROM apple_songs_performance
                ORDER BY plays DESC
                LIMIT 10
            """
            df_top_plays = db.fetch_df(top_plays_query)
            
            if not df_top_plays.empty:
                fig = px.bar(
                    df_top_plays,
                    x='plays',
                    y='song_name',
                    orientation='h',
                    title='Top 10 Chansons par Nombre de Plays',
                    labels={'plays': 'Nombre de Plays', 'song_name': 'Chanson'},
                    color='plays',
                    color_continuous_scale='Blues'
                )
                fig.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("📭 Aucune donnée disponible pour le moment")
        
        with tab2:
            # Top 10 par listeners
            top_listeners_query = """
                SELECT 
                    song_name,
                    album_name,
                    plays,
                    listeners,
                    collected_at
                FROM apple_songs_performance
                WHERE listeners > 0
                ORDER BY listeners DESC
                LIMIT 10
            """
            df_top_listeners = db.fetch_df(top_listeners_query)
            
            if not df_top_listeners.empty:
                fig = px.bar(
                    df_top_listeners,
                    x='listeners',
                    y='song_name',
                    orientation='h',
                    title='Top 10 Chansons par Nombre de Listeners',
                    labels={'listeners': 'Nombre de Listeners', 'song_name': 'Chanson'},
                    color='listeners',
                    color_continuous_scale='Greens'
                )
                fig.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("📭 Aucune donnée disponible pour le moment")
        
        with tab3:
            # Tableau détaillé
            all_songs_query = """
                SELECT 
                    song_name as "Chanson",
                    album_name as "Album",
                    plays as "Plays",
                    listeners as "Listeners",
                    ROUND(CAST(plays AS NUMERIC) / NULLIF(listeners, 0), 2) as "Plays/Listener",
                    TO_CHAR(collected_at, 'DD/MM/YYYY HH24:MI') as "Collecté le"
                FROM apple_songs_performance
                ORDER BY plays DESC
            """
            df_all_songs = db.fetch_df(all_songs_query)
            
            if not df_all_songs.empty:
                st.dataframe(
                    df_all_songs,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Bouton d'export CSV
                csv = df_all_songs.to_csv(index=False)
                st.download_button(
                    label="📥 Télécharger en CSV",
                    data=csv,
                    file_name=f"apple_music_songs_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("📭 Aucune donnée disponible pour le moment")
        
        st.markdown("---")
        
        # ============================================================
        # ÉVOLUTION TEMPORELLE (si données daily_plays disponibles)
        # ============================================================
        daily_count = db.get_table_count('apple_daily_plays')
        
        if daily_count > 0:
            st.subheader("📈 Évolution des Plays")
            
            # Sélecteur de chanson
            songs_list_query = """
                SELECT DISTINCT song_name
                FROM apple_daily_plays
                ORDER BY song_name
            """
            df_songs = db.fetch_df(songs_list_query)
            
            if not df_songs.empty:
                selected_songs = st.multiselect(
                    "Sélectionnez les chansons à afficher",
                    options=df_songs['song_name'].tolist(),
                    default=df_songs['song_name'].tolist()[:3] if len(df_songs) >= 3 else df_songs['song_name'].tolist()
                )
                
                if selected_songs:
                    # Récupérer les données temporelles
                    placeholders = ','.join(['%s'] * len(selected_songs))
                    timeline_query = f"""
                        SELECT 
                            date,
                            song_name,
                            plays
                        FROM apple_daily_plays
                        WHERE song_name IN ({placeholders})
                        ORDER BY date, song_name
                    """
                    df_timeline = db.fetch_df(timeline_query, tuple(selected_songs))
                    
                    if not df_timeline.empty:
                        fig = px.line(
                            df_timeline,
                            x='date',
                            y='plays',
                            color='song_name',
                            title='Évolution des Plays par Chanson',
                            labels={'date': 'Date', 'plays': 'Nombre de Plays', 'song_name': 'Chanson'},
                            markers=True
                        )
                        fig.update_layout(hovermode='x unified')
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("📭 Aucune donnée temporelle disponible pour ces chansons")
                else:
                    st.info("👆 Sélectionnez au moins une chanson")
            
            st.markdown("---")
        
        # ============================================================
        # ÉVOLUTION DES LISTENERS (si données disponibles)
        # ============================================================
        listeners_count = db.get_table_count('apple_listeners')
        
        if listeners_count > 0:
            st.subheader("👥 Évolution des Listeners")
            
            listeners_query = """
                SELECT 
                    date,
                    listeners
                FROM apple_listeners
                ORDER BY date
            """
            df_listeners = db.fetch_df(listeners_query)
            
            if not df_listeners.empty:
                fig = px.area(
                    df_listeners,
                    x='date',
                    y='listeners',
                    title='Évolution du Nombre de Listeners',
                    labels={'date': 'Date', 'listeners': 'Nombre de Listeners'},
                    color_discrete_sequence=['#34C759']
                )
                fig.update_traces(line_shape='spline')
                st.plotly_chart(fig, use_container_width=True)
                
                # Stats sur les listeners
                col1, col2, col3 = st.columns(3)
                
                avg_listeners = df_listeners['listeners'].mean()
                max_listeners = df_listeners['listeners'].max()
                min_listeners = df_listeners['listeners'].min()
                
                col1.metric("📊 Moyenne", f"{int(avg_listeners):,}")
                col2.metric("⬆️ Maximum", f"{int(max_listeners):,}")
                col3.metric("⬇️ Minimum", f"{int(min_listeners):,}")
            else:
                st.info("📭 Aucune donnée de listeners disponible")
            
            st.markdown("---")
        
        # ============================================================
        # INSTRUCTIONS D'UTILISATION
        # ============================================================
        with st.expander("💡 Comment importer des données Apple Music ?"):
            st.markdown("""
            ### 📥 Importer des données depuis Apple Music for Artists
            
            1. **Connectez-vous à** [Apple Music for Artists](https://artists.apple.com)
            
            2. **Exportez vos données :**
               - Accédez à la section "Analytics" ou "Insights"
               - Sélectionnez la période souhaitée
               - Cliquez sur "Export" ou "Download CSV"
            
            3. **Déposez les fichiers CSV :**
               ```
               data/raw/apple_music/
               ```
            
            4. **Lancez le traitement :**
               - Via Streamlit : Utilisez le bouton "🍎 CSV Apple" dans la sidebar
               - Via script : `python process_apple_music_csv.py`
               - Automatique : Le DAG Airflow surveille le dossier toutes les 15 minutes
            
            ### 📊 Types de CSV supportés :
            - **Songs Performance** : Liste des chansons avec plays et listeners
            - **Daily Plays** : Évolution quotidienne des plays par chanson
            - **Listeners** : Évolution quotidienne du nombre de listeners
            
            ### ⚠️ Notes :
            - Les fichiers sont automatiquement archivés après traitement
            - Les données sont dédupliquées (upsert)
            - Rafraîchissez la page après import pour voir les nouvelles données
            """)
    
    except Exception as e:
        st.error(f"❌ Erreur lors du chargement des données : {e}")
        import traceback
        st.code(traceback.format_exc())
    
    finally:
        db.close()


if __name__ == "__main__":
    show()