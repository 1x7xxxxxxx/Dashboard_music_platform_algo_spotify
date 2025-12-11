"""Application Streamlit principale avec déclenchement des DAGs."""
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import sys
from datetime import datetime
from dotenv import load_dotenv
import os

# ✅ IMPORTANT : Ajouter le chemin AVANT les imports src.*
sys.path.append(str(Path(__file__).parent.parent.parent))

# ✅ Charger .env.local si disponible
env_file = '.env.local' if os.path.exists('.env.local') else '.env'
load_dotenv(env_file)

from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader
from src.utils.airflow_trigger import AirflowTrigger

# ⚠️ FILTRE ARTISTE (Pour exclure la ligne "Total" des CSV)
ARTIST_NAME_FILTER = "1x7xxxxxxx"

st.set_page_config(page_title="Music Dashboard", page_icon="🎵", layout="wide")

config = config_loader.load()
airflow_config = config.get('airflow', {})
airflow_trigger = AirflowTrigger(
    base_url=airflow_config.get('base_url', 'http://localhost:8080'),
    username=airflow_config.get('username', 'admin'),
    password=airflow_config.get('password', 'admin')
)

def get_db():
    config = config_loader.load()
    db_config = config['database']
    return PostgresHandler(**db_config)

def show_navigation_menu():
    st.sidebar.title("🎵 Navigation")
    pages = {
        "🏠 Accueil": "home",
        "📱 Meta Ads - Vue d'ensemble": "meta_ads_overview",
        "🎵 META x Spotify": "meta_x_spotify",
        "🎵 Spotify & S4A": "spotify_s4a_combined",
        "📱 Hypeddit": "hypeddit",
        "☁️ SoundCloud": "soundcloud",
        "📸 Instagram": "instagram",
        "🎎 Apple Music": "apple_music",
        "🎬 YouTube": "youtube",
        "🏗️ Monitoring ETL": "airflow_kpi",
    }
    return pages[st.sidebar.radio("Aller à ", list(pages.keys()), label_visibility="collapsed")]

def show_data_collection_panel():
    st.sidebar.markdown("---")
    if st.sidebar.button("🚀 Lancer TOUTES les collectes", type="primary"):
        with st.sidebar.status("Synchronisation...", expanded=True):
            dags = [("spotify_api_daily", "Spotify"), ("youtube_daily", "YouTube"),
                    ("soundcloud_daily", "SoundCloud"), ("instagram_daily", "Instagram"),
                    ("s4a_csv_watcher", "CSV S4A"), ("apple_music_csv_watcher", "CSV Apple"),
                    ("meta_csv_watcher_config", "Meta Config"), ("meta_insights_watcher", "Meta Stats")]
            for dag_id, label in dags:
                try:
                    if airflow_trigger.trigger_dag(dag_id).get('success'): st.write(f"✅ {label}")
                    else: st.error(f"❌ {label}")
                except: st.error(f"❌ {label}")
            st.sidebar.success("Lancé !")

def get_spotify_chart_data(db):
    """Récupère l'historique dédupliqué (MAX par jour)."""
    try:
        # On utilise MAX(streams) groupé par date et chanson pour écraser les doublons
        # Puis on somme par date
        query = """
            SELECT date, SUM(daily_max) as value, 'Spotify' as platform
            FROM (
                SELECT date, song, MAX(streams) as daily_max
                FROM s4a_song_timeline
                WHERE song NOT ILIKE %s
                GROUP BY date, song
            ) sub
            GROUP BY date
            ORDER BY date ASC
        """
        df = db.fetch_df(query, (f"%{ARTIST_NAME_FILTER}%",))
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df['value'] = df['value'].cumsum() # Cumulatif pour voir la croissance
            return df
    except: pass
    return pd.DataFrame()

def main():
    page = show_navigation_menu()
    show_data_collection_panel()
    
    if page == "home":
        st.title("🎵 Music Platform Dashboard")
        st.markdown("---")
        
        db = get_db()
        try:
            # 1. SPOTIFY : Somme des MAX par chanson (Total Nettoyé)
            q_spot = """
                SELECT SUM(streams) FROM (
                    SELECT song, MAX(streams) as streams
                    FROM (
                        SELECT date, song, MAX(streams) as streams 
                        FROM s4a_song_timeline 
                        WHERE song NOT ILIKE %s 
                        GROUP BY date, song
                    ) daily_deduped
                    GROUP BY song
                ) total_deduped
            """
            # Note: Cette logique prend le MAX atteint par chaque chanson (somme des pics)
            # Alternative : Somme de tous les jours uniques :
            q_spot_alt = """
                SELECT SUM(daily_max) FROM (
                    SELECT date, song, MAX(streams) as daily_max
                    FROM s4a_song_timeline
                    WHERE song NOT ILIKE %s
                    GROUP BY date, song
                ) sub
            """
            total_spotify = db.fetch_query(q_spot_alt, (f"%{ARTIST_NAME_FILTER}%",))[0][0] or 0
            
            # 2. YOUTUBE : On prend le MAX de vues connu par video_id
            # On cherche dans youtube_video_stats qui contient l'historique
            try:
                q_yt = """
                    SELECT SUM(max_views) FROM (
                        SELECT video_id, MAX(view_count) as max_views 
                        FROM youtube_video_stats 
                        GROUP BY video_id
                    ) sub
                """
                total_yt = db.fetch_query(q_yt)[0][0] or 0
            except: total_yt = 0
            
            # 3. SOUNDCLOUD & APPLE (inchangés)
            try: total_sc = db.fetch_query("SELECT SUM(playback_count) FROM view_soundcloud_latest")[0][0] or 0
            except: total_sc = 0
            try: total_apple = db.fetch_query("SELECT SUM(plays) FROM apple_songs_performance")[0][0] or 0
            except: total_apple = 0
            
            GRAND_TOTAL = total_spotify + total_apple + total_sc + total_yt

            st.markdown(f"""
            <div style="text-align: center; padding: 20px; background-color: #f0f2f6; border-radius: 10px; margin-bottom: 20px;">
                <h2 style="color: #555; margin:0;">🎧 Total Streams</h2>
                <h1 style="font-size: 3.5em; color: #1DB954; margin:0;">{int(GRAND_TOTAL):,}</h1>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Spotify", f"{int(total_spotify):,}")
            c2.metric("YouTube", f"{int(total_yt):,}")
            c3.metric("SoundCloud", f"{int(total_sc):,}")
            c4.metric("Apple Music", f"{int(total_apple):,}")
            
            st.markdown("---")
            st.subheader("📈 Évolution Cumulée (Spotify)")
            
            df_chart = get_spotify_chart_data(db)
            if not df_chart.empty:
                fig = px.area(df_chart, x="date", y="value", color="platform", 
                              color_discrete_map={"Spotify": "#1DB954"})
                fig.update_layout(yaxis_title="Streams Cumulés", hovermode="x unified")
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("Pas assez de données.")

        except Exception as e:
            st.error(f"Erreur : {e}")
        finally:
            db.close()
            
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1: 
            if st.button("🔗 Airflow UI"): st.markdown("[Ouvrir](http://localhost:8080)")
        with c2: st.code("docker-compose up -d")

    # Routing
    elif page == "meta_ads_overview": from views.meta_ads_overview import show; show()
    elif page == "meta_x_spotify": from views.meta_x_spotify import show; show()
    elif page == "spotify_s4a_combined": from views.spotify_s4a_combined import show; show()
    elif page == "hypeddit": from views.hypeddit import show; show()
    elif page == "apple_music": from views.apple_music import show; show()
    elif page == "youtube": from views.youtube import show; show()
    elif page == "soundcloud": from views.soundcloud import show; show()
    elif page == "instagram": from views.instagram import show; show()
    elif page == "airflow_kpi": from views.airflow_kpi import show; show()

if __name__ == "__main__":
    main()