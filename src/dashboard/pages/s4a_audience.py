"""Page Audience S4A."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
    """Affiche la page Audience."""
    st.title("👥 Analyse de l'Audience")
    st.markdown("---")
    
    db = get_db()
    
    # Récupérer données
    query = """
        SELECT date, listeners, streams, followers
        FROM s4a_audience
        ORDER BY date
    """
    
    df = db.fetch_df(query)
    
    if df.empty:
        st.warning("Aucune donnée d'audience disponible")
        db.close()
        return
    
    df['date'] = pd.to_datetime(df['date'])
    
    # KPIs actuels
    st.header("🎯 Métriques Actuelles")
    
    current = df.iloc[-1]
    previous = df.iloc[-8] if len(df) >= 8 else df.iloc[0]
    
    col1, col2, col3 = st.columns(3)
    
    followers_delta = current['followers'] - previous['followers']
    col1.metric(
        "👥 Followers",
        f"{current['followers']:,}",
        f"{followers_delta:+,} (7j)"
    )
    
    listeners_7d = df.tail(7)['listeners'].sum()
    col2.metric(
        "🎧 Listeners (7j)",
        f"{listeners_7d:,}"
    )
    
    streams_7d = df.tail(7)['streams'].sum()
    col3.metric(
        "📊 Streams (7j)",
        f"{streams_7d:,}"
    )
    
    st.markdown("---")
    
    # Graphique évolution
    st.header("📈 Évolution dans le Temps")
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['streams'],
        name='Streams',
        mode='lines',
        line=dict(color='#1DB954', width=2),
        fill='tonexty'
    ))
    
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['listeners'],
        name='Listeners',
        mode='lines',
        line=dict(color='#1ed760', width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['followers'],
        name='Followers',
        mode='lines',
        line=dict(color='#ff6b6b', width=2),
        yaxis='y2'
    ))
    
    fig.update_layout(
        title="Évolution Streams / Listeners / Followers",
        xaxis_title="Date",
        yaxis_title="Streams & Listeners",
        yaxis2=dict(
            title="Followers",
            overlaying='y',
            side='right'
        ),
        height=600,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Statistiques par période
    st.header("📊 Statistiques par Période")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("7 derniers jours")
        df_7d = df.tail(7)
        st.metric("Streams", f"{df_7d['streams'].sum():,}")
        st.metric("Listeners uniques", f"{df_7d['listeners'].sum():,}")
        st.metric("Moy. Streams/jour", f"{df_7d['streams'].mean():,.0f}")
    
    with col2:
        st.subheader("30 derniers jours")
        df_30d = df.tail(30)
        st.metric("Streams", f"{df_30d['streams'].sum():,}")
        st.metric("Listeners uniques", f"{df_30d['listeners'].sum():,}")
        st.metric("Moy. Streams/jour", f"{df_30d['streams'].mean():,.0f}")
    
    with col3:
        st.subheader("Tout le temps")
        st.metric("Streams", f"{df['streams'].sum():,}")
        st.metric("Listeners uniques", f"{df['listeners'].sum():,}")
        st.metric("Jours de données", f"{len(df)}")
    
    st.markdown("---")
    
    # Tableau détaillé
    st.header("📋 Détails Quotidiens (30 derniers jours)")
    
    df_display = df.tail(30).sort_values('date', ascending=False)
    df_display['date'] = df_display['date'].dt.strftime('%Y-%m-%d')
    
    st.dataframe(
        df_display,
        hide_index=True,
        use_container_width=True,
        height=400
    )
    
    db.close()


if __name__ == "__main__":
    show()