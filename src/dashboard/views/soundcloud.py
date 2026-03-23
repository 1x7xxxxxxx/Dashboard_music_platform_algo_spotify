import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id

def show():
    st.title("☁️ SoundCloud - Performance")
    st.markdown("---")

    db = get_db_connection()
    artist_id = get_artist_id() or 1

    # =========================================================================
    # 1. KPIs GLOBAUX (Dernière date connue)
    # =========================================================================
    try:
        df_latest = db.fetch_df("""
            SELECT DISTINCT ON (track_id)
                track_id, title, permalink_url, playback_count,
                likes_count, reposts_count, comment_count, collected_at
            FROM soundcloud_tracks_daily
            WHERE artist_id = %s
            ORDER BY track_id, collected_at DESC
        """, (artist_id,))
        
        if not df_latest.empty:
            # Calculs
            total_plays = df_latest['playback_count'].sum()
            total_likes = df_latest['likes_count'].sum()
            total_reposts = df_latest['reposts_count'].sum()
            total_comments = df_latest['comment_count'].sum()
            total_tracks = len(df_latest)
            
            # Récupération de la dernière date de collecte
            last_date_str = pd.to_datetime(df_latest['collected_at']).max().strftime('%d/%m/%Y')

            # Affichage sur 2 lignes
            c1, c2, c3 = st.columns(3)
            c1.metric("🎧 Total Écoutes", f"{int(total_plays):,}")
            c2.metric("❤️ Total Likes", f"{int(total_likes):,}")
            c3.metric("🔄 Total Reposts", f"{int(total_reposts):,}")
            
            c4, c5, c6 = st.columns(3)
            c4.metric("💬 Total Commentaires", f"{int(total_comments):,}")
            c5.metric("🎵 Titres en ligne", total_tracks)
            c6.metric("📅 Dernière mise à jour", last_date_str)
            
        else:
            st.warning("Aucune donnée SoundCloud trouvée. Lancez le collecteur.")
            db.close()
            return

    except Exception as e:
        st.error(f"Erreur SQL (KPIs) : {e}")
        db.close()
        return

    st.markdown("---")

    # =========================================================================
    # 2. ANALYSE TEMPORELLE (Filtres Dynamiques)
    # =========================================================================
    st.subheader("📈 Évolution des écoutes")
    
    # --- FILTRES ---
    with st.expander("⚙️ Filtres du graphique", expanded=True):
        col_f1, col_f2 = st.columns(2)
        
        # A. Filtre Période (Défaut : 30 derniers jours)
        today = datetime.now().date()
        start_default = today - timedelta(days=30)
        
        date_range = col_f1.date_input(
            "Période",
            value=(start_default, today),
            max_value=today,
            format="DD/MM/YYYY"
        )
        
        # B. Filtre Titres (Multiselect) — trié par streams desc (plus actif en premier)
        all_titles = df_latest.sort_values('playback_count', ascending=False)['title'].tolist()
        selected_tracks = col_f2.multiselect(
            "Filtrer par titres",
            options=all_titles,
            default=all_titles  # Tout sélectionné par défaut
        )

    # --- REQUÊTE & AFFICHAGE ---
    try:
        # Gestion sécurisée des dates (si l'utilisateur ne sélectionne qu'une date)
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_d, end_d = date_range
        else:
            start_d = start_default
            end_d = today

        # On récupère l'historique large (on filtre en Pandas pour plus de souplesse UI)
        query_hist = """
            SELECT collected_at, title, playback_count
            FROM soundcloud_tracks_daily
            WHERE artist_id = %s
            ORDER BY collected_at ASC
        """
        df_history = db.fetch_df(query_hist, (artist_id,))
        
        if not df_history.empty:
            # Conversion types
            df_history['collected_at'] = pd.to_datetime(df_history['collected_at']).dt.date
            
            # APPLICATION DES FILTRES
            mask_date = (df_history['collected_at'] >= start_d) & (df_history['collected_at'] <= end_d)
            mask_track = df_history['title'].isin(selected_tracks)
            
            df_filtered = df_history[mask_date & mask_track]
            
            if not df_filtered.empty:
                # Graphique linéaire
                fig = px.line(
                    df_filtered, 
                    x='collected_at', 
                    y='playback_count', 
                    color='title',
                    title=f"Croissance ({start_d.strftime('%d/%m')} - {end_d.strftime('%d/%m')})",
                    markers=True
                )
                fig.update_layout(
                    xaxis_title="Date", 
                    yaxis_title="Écoutes Cumulées",
                    hovermode="x unified",
                    legend=dict(orientation="h", y=-0.2) # Légende en bas pour ne pas cacher
                )
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("Aucune donnée pour cette sélection (Vérifiez les dates ou les titres).")
        else:
            st.info("Historique vide pour le moment.")
            
    except Exception as e:
        st.error(f"Erreur historique : {e}")

    st.markdown("---")

    # =========================================================================
    # 3. TOP TITRES (Tableau épuré)
    # =========================================================================
    st.subheader("🏆 Top Titres")
    if not df_latest.empty:
        # Tri et Sélection des colonnes (Sans permalink_url)
        df_top = df_latest.sort_values(by='playback_count', ascending=False)
        
        # On ne garde que les colonnes utiles
        cols_to_show = ['title', 'playback_count', 'likes_count', 'reposts_count', 'comment_count']
        
        st.dataframe(
            df_top[cols_to_show],
            column_config={
                "title": "Titre",
                "playback_count": st.column_config.NumberColumn("Écoutes", format="%d"),
                "likes_count": st.column_config.NumberColumn("❤️ Likes", format="%d"),
                "reposts_count": st.column_config.NumberColumn("🔄 Reposts", format="%d"),
                "comment_count": st.column_config.NumberColumn("💬 Coms", format="%d")
            },
            hide_index=True,
            width='stretch'
        )

    db.close()

if __name__ == "__main__":
    show()