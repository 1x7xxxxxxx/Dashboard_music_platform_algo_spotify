"""Application Streamlit principale avec déclenchement des DAGs."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sys
from datetime import datetime, timedelta
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

# Configuration de la page
st.set_page_config(
    page_title="Music Platform Dashboard",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialiser AirflowTrigger
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
    return PostgresHandler(
        host=db_config['host'],
        port=db_config['port'],
        database=db_config['database'],
        user=db_config['user'],
        password=db_config['password']
    )

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
    selection = st.sidebar.radio("Aller à ", list(pages.keys()), label_visibility="collapsed")
    return pages[selection]

def show_data_collection_panel():
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔄 Synchronisation")
    
    if st.sidebar.button("🚀 Lancer TOUTES les collectes", type="primary"):
        with st.sidebar.status("Démarrage des pipelines...", expanded=True) as status:
            dags_to_run = [
                ("spotify_api_daily", "Spotify API"),
                ("youtube_daily", "YouTube Data"),
                ("soundcloud_daily", "SoundCloud Data"),
                ("instagram_daily", "Instagram Data"),
                ("s4a_csv_watcher", "CSV Spotify Artists"),
                ("apple_music_csv_watcher", "CSV Apple Music"),
                ("meta_csv_watcher_config", "Meta Ads (Config)"),
                ("meta_insights_watcher", "Meta Ads (Stats)"),
                ("data_quality_check", "Check Qualité")
            ]
            success_count = 0
            for dag_id, label in dags_to_run:
                st.write(f"⏳ {label}...")
                try:
                    res = airflow_trigger.trigger_dag(dag_id)
                    if res.get('success'):
                        st.write(f"✅ {label}")
                        success_count += 1
                    else:
                        st.error(f"❌ {label}: {res.get('error')}")
                except Exception as e: st.error(f"❌ {label}: {e}")
            
            if success_count == len(dags_to_run):
                status.update(label="✅ Tout est lancé !", state="complete")
                st.sidebar.success("Rafraîchissez dans quelques minutes.")
    
    st.sidebar.caption("Traite les API et les CSV du dossier `data/raw`.")
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 🛠️ Collectes Individuelles")
    
    c1, c2 = st.sidebar.columns(2)
    with c1:
        if st.button("🎸 Spotify", help="API"): airflow_trigger.trigger_dag('spotify_api_daily')
        if st.button("🎵 S4A", help="CSV"): airflow_trigger.trigger_dag('s4a_csv_watcher')
        if st.button("📱 Meta", help="CSV"): 
            airflow_trigger.trigger_dag('meta_csv_watcher_config')
            airflow_trigger.trigger_dag('meta_insights_watcher')
        if st.button("📸 Insta", help="API"): airflow_trigger.trigger_dag('instagram_daily')
    with c2:
        if st.button("🎎 Apple", help="CSV"): airflow_trigger.trigger_dag('apple_music_csv_watcher')
        if st.button("🎬 YouTube", help="API"): airflow_trigger.trigger_dag('youtube_daily')
        if st.button("☁️ S-Cloud", help="API"): airflow_trigger.trigger_dag('soundcloud_daily')

def get_spotify_chart_data(db):
    """Récupère l'historique propre pour le graphique (Uniquement Spotify)."""
    try:
        # On utilise DISTINCT ON pour ne garder qu'une seule valeur par jour/chanson (élimine les doublons)
        df = db.fetch_df("""
            SELECT date, SUM(streams) as value, 'Spotify' as platform
            FROM (
                SELECT DISTINCT ON (date, song) streams, date
                FROM s4a_song_timeline
                ORDER BY date, song, collected_at DESC
            ) sub
            GROUP BY date
            ORDER BY date ASC
        """)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df['value'] = df['value'].cumsum()
            return df
    except: pass
    return pd.DataFrame()

def main():
    page = show_navigation_menu()
    show_data_collection_panel()
    
    if page == "home":
        st.title("🎵 Music Platform Dashboard")
        st.markdown("---")
        
        # --- SECTION 1 : APERÇU RAPIDE & TOTAL STREAMS ---
        db = get_db()
        try:
            total_spotify = 0
            total_apple = 0
            total_sc = 0
            total_yt = 0
            
            # 1. Spotify (Total S4A Nettoyé)
            # Cette requête prend chaque jour unique pour chaque chanson et les additionne.
            # Elle ignore les doublons s'ils existent dans la base.
            try: 
                query_spot = """
                    SELECT SUM(streams) 
                    FROM (
                        SELECT DISTINCT ON (date, song) streams 
                        FROM s4a_song_timeline 
                        ORDER BY date, song, collected_at DESC
                    ) sub
                """
                total_spotify = db.fetch_query(query_spot)[0][0] or 0
            except: pass
            
            # 2. Apple (Somme des plays)
            try: total_apple = db.fetch_query("SELECT SUM(plays) FROM apple_songs_performance")[0][0] or 0
            except: pass
            
            # 3. SoundCloud (Somme des playbacks du dernier snapshot par track)
            try: total_sc = db.fetch_query("SELECT SUM(playback_count) FROM view_soundcloud_latest")[0][0] or 0
            except: pass
            
            # 4. YouTube (Somme des vues de la DERNIÈRE capture connue par vidéo)
            try:
                query_yt = """
                    SELECT SUM(view_count) 
                    FROM (
                        SELECT DISTINCT ON (video_id) view_count 
                        FROM youtube_videos 
                        ORDER BY video_id, collected_at DESC
                    ) sub
                """
                total_yt = db.fetch_query(query_yt)[0][0] or 0
            except: pass
            
            GRAND_TOTAL = total_spotify + total_apple + total_sc + total_yt

            # Affichage "Big Number"
            st.markdown(f"""
            <div style="text-align: center; padding: 20px; background-color: #f0f2f6; border-radius: 10px; margin-bottom: 20px;">
                <h2 style="color: #555; margin:0;">🎧 Total Streams (Toutes Plateformes)</h2>
                <h1 style="font-size: 3.5em; color: #1DB954; margin:0;">{int(GRAND_TOTAL):,}</h1>
            </div>
            """, unsafe_allow_html=True)
            
            # KPIs individuels
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Spotify", f"{int(total_spotify):,}")
            c2.metric("YouTube", f"{int(total_yt):,}")
            c3.metric("SoundCloud", f"{int(total_sc):,}")
            c4.metric("Apple Music", f"{int(total_apple):,}")
            
            st.markdown("---")
            
            # --- SECTION 2 : GRAPHIQUE ÉVOLUTION (SPOTIFY ONLY) ---
            st.subheader("📈 Évolution Cumulée des Streams (Spotify)")
            
            df_chart = get_spotify_chart_data(db)
            
            if not df_chart.empty:
                fig = px.area(
                    df_chart, 
                    x="date", 
                    y="value", 
                    color="platform",
                    title="Croissance Spotify",
                    color_discrete_map={"Spotify": "#1DB954"}
                )
                fig.update_layout(xaxis_title="Date", yaxis_title="Streams Cumulés", hovermode="x unified")
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("Aucune donnée Spotify pour le graphique. Avez-vous importé les CSV ?")

        except Exception as e:
            st.error(f"Erreur chargement données: {e}")
        finally:
            db.close()
        
        st.markdown("---")
        
        # --- SECTION 3 : INFRASTRUCTURE ---
        st.subheader("🔧 Infrastructure & Commandes")
        col1, col2 = st.columns(2)
        
        with col1:
            st.info("**Interface Airflow:** http://localhost:8080")
            if st.button("🔗 Ouvrir Airflow UI"):
                st.markdown("[Cliquez ici](http://localhost:8080)")
                
        with col2:
            st.info("**Commande Docker (Démarrage):**")
            st.code("docker-compose up -d", language="bash")
            st.caption("À exécuter dans le terminal si Airflow est éteint.")

    # --- ROUTING DES AUTRES PAGES ---
    elif page == "meta_ads_overview":
        from views.meta_ads_overview import show
        show()
    elif page == "meta_x_spotify":
        from views.meta_x_spotify import show
        show()
    elif page == "spotify_s4a_combined":
        from views.spotify_s4a_combined import show
        show()
    elif page == "hypeddit":
        from views.hypeddit import show
        show()
    elif page == "apple_music":
        from views.apple_music import show
        show()
    elif page == "youtube":
        from views.youtube import show
        show()
    elif page == "soundcloud": 
        from views.soundcloud import show
        show()
    elif page == "instagram":
        from views.instagram import show
        show()
    elif page == "airflow_kpi":
        from views.airflow_kpi import show
        show()

if __name__ == "__main__":
    main()