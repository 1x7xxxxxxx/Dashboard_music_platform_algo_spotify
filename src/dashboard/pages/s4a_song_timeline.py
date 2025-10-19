"""Page Timeline par chanson S4A."""
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

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
    """Affiche la page Timeline par chanson."""
    st.title("🎸 Timeline Détaillée par Chanson")
    st.markdown("---")
    
    db = get_db()
    
    # Récupérer liste des chansons
    songs_query = "SELECT DISTINCT song FROM s4a_song_timeline ORDER BY song"
    songs = [row[0] for row in db.fetch_query(songs_query)]
    
    if not songs:
        st.warning("Aucune chanson trouvée dans la base de données")
        db.close()
        return
    
    # Sélection chanson
    selected_song = st.selectbox("🎵 Sélectionnez une chanson", songs)
    
    st.markdown("---")
    
    # Récupérer données timeline
    timeline_query = """
        SELECT date, streams
        FROM s4a_song_timeline
        WHERE song = %s
        ORDER BY date
    """
    
    df = db.fetch_df(timeline_query, (selected_song,))
    
    if df.empty:
        st.warning(f"Aucune donnée timeline pour '{selected_song}'")
        db.close()
        return
    
    df['date'] = pd.to_datetime(df['date'])
    
    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    
    total_streams = df['streams'].sum()
    col1.metric("🎧 Streams Totaux", f"{total_streams:,}")
    
    avg_daily = df['streams'].mean()
    col2.metric("📊 Moy. quotidienne", f"{avg_daily:,.0f}")
    
    best_day_streams = df['streams'].max()
    col3.metric("🔥 Meilleur jour", f"{best_day_streams:,}")
    
    days_with_data = len(df[df['streams'] > 0])
    col4.metric("📅 Jours actifs", f"{days_with_data}")
    
    st.markdown("---")
    
    # Graphique principal
    st.subheader("📈 Évolution des Streams")
    
    fig = px.area(
        df,
        x='date',
        y='streams',
        title=f"Timeline: {selected_song}",
        labels={'date': 'Date', 'streams': 'Streams'},
        color_discrete_sequence=['#1DB954']
    )
    
    fig.update_layout(
        height=500,
        hovermode='x unified',
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Statistiques par période
    st.subheader("📊 Statistiques par Période")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 7 derniers jours
        df_last_7 = df.tail(7)
        streams_7d = df_last_7['streams'].sum()
        st.metric("Streams (7 derniers jours)", f"{streams_7d:,}")
    
    with col2:
        # 30 derniers jours
        df_last_30 = df.tail(30)
        streams_30d = df_last_30['streams'].sum()
        st.metric("Streams (30 derniers jours)", f"{streams_30d:,}")
    
    # Tableau détaillé
    st.subheader("📋 Détails par Jour (20 derniers)")
    
    df_display = df.tail(20).sort_values('date', ascending=False)
    df_display['date'] = df_display['date'].dt.strftime('%Y-%m-%d')
    
    st.dataframe(
        df_display,
        hide_index=True,
        use_container_width=True
    )
    
    db.close()


if __name__ == "__main__":
    show()