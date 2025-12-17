import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import timedelta
from src.dashboard.utils import get_db_connection

def show():
    st.title("🚀 Road to Algorithms (J+28)")
    st.markdown("Suivi de l'activation des algorithmes Spotify (Release Radar & Discover Weekly).")
    
    db = get_db_connection()

    # 1. Sélection du Titre
    try:
        # On ne prend que les titres qui ont des données timeline
        q_tracks = "SELECT DISTINCT song FROM s4a_song_timeline ORDER BY song"
        tracks = db.fetch_df(q_tracks)['song'].tolist()
    except: tracks = []

    if not tracks:
        st.warning("Aucune donnée de timeline disponible.")
        return

    selected_track = st.selectbox("Sélectionner un titre", tracks)

    # 2. Récupération & Traitement des données
    # On récupère tout l'historique, mais on va calculer le J+0 (Date de sortie) dynamiquement
    q_data = """
        SELECT date, streams 
        FROM s4a_song_timeline 
        WHERE song = %s 
        ORDER BY date ASC
    """
    df_streams = db.fetch_df(q_data, (selected_track,))

    # Récupération Popularité
    q_pop = """
        SELECT date, popularity 
        FROM track_popularity_history 
        WHERE track_name = %s 
        ORDER BY date ASC
    """
    df_pop = db.fetch_df(q_pop, (selected_track,))

    if df_streams.empty:
        st.error("Pas de données de streams pour ce titre.")
        return

    # --- LOGIQUE J+28 ---
    # La date de sortie est supposée être la première date où on a des streams (ou la première date en base)
    release_date = pd.to_datetime(df_streams['date'].min())
    end_date_28 = release_date + timedelta(days=28)

    # Conversion en datetime
    df_streams['date'] = pd.to_datetime(df_streams['date'])
    
    # Filtrage strict J+0 à J+28
    mask = (df_streams['date'] >= release_date) & (df_streams['date'] <= end_date_28)
    df_focus = df_streams.loc[mask].copy()
    
    # Création de l'axe "Jour depuis sortie" (0, 1, 2... 28)
    df_focus['day_index'] = (df_focus['date'] - release_date).dt.days
    
    # Calcul Cumulé (C'est ça qui compte pour les algos)
    df_focus['streams_cumul'] = df_focus['streams'].cumsum()

    # Merge Popularité (Left join sur la date)
    if not df_pop.empty:
        df_pop['date'] = pd.to_datetime(df_pop['date'])
        df_focus = pd.merge(df_focus, df_pop, on='date', how='left')
        df_focus['popularity'] = df_focus['popularity'].ffill().fillna(0) # Lissage
    else:
        df_focus['popularity'] = 0

    # --- MÉTRIQUES ACTUELLES ---
    current_total = df_focus['streams_cumul'].max()
    current_pop = df_focus['popularity'].iloc[-1] if not df_focus.empty else 0
    days_elapsed = df_focus['day_index'].max()

    # Seuils (Hard-coded heuristics)
    GOAL_RR_STREAMS = 1000
    GOAL_DW_STREAMS = 10000
    GOAL_DW_POP = 30

    # Calcul des pourcentages
    pct_rr = min(current_total / GOAL_RR_STREAMS, 1.0)
    pct_dw_streams = min(current_total / GOAL_DW_STREAMS, 1.0)
    pct_dw_pop = min(current_pop / GOAL_DW_POP, 1.0)
    
    # Score global DW (Moyenne pondérée ou condition stricte)
    # Ici condition stricte : il faut les deux
    pct_dw_global = (pct_dw_streams + pct_dw_pop) / 2

    # --- AFFICHAGE KPI ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Jours écoulés", f"{days_elapsed}/28", delta=f"{28-days_elapsed} restants", delta_color="inverse")
    c2.metric("Streams Cumulés (J+28)", f"{current_total:,.0f}")
    c3.metric("Popularité Actuelle", f"{current_pop:.0f}/100")

    st.markdown("---")

    # --- BARRES DE PROGRESSION (GAMIFICATION) ---
    st.subheader("🎯 Objectifs Algorithmiques")
    
    # Release Radar
    st.write(f"**📡 Release Radar** ({int(pct_rr*100)}%)")
    st.progress(pct_rr)
    if pct_rr >= 1.0: st.caption("✅ Trigger théoriquement activé !")
    else: st.caption(f"Manque {GOAL_RR_STREAMS - current_total:,.0f} streams")

    # Discover Weekly
    st.write(f"**💎 Discover Weekly** ({int(pct_dw_global*100)}%)")
    st.progress(pct_dw_global)
    c_dw1, c_dw2 = st.columns(2)
    c_dw1.info(f"Critère Streams : {int(pct_dw_streams*100)}% (Obj: 10k)")
    c_dw2.info(f"Critère Pop : {int(pct_dw_pop*100)}% (Obj: 30)")

    st.markdown("---")

    # --- GRAPHIQUE AVANCÉ ---
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 1. Courbe Streams Cumulés
    fig.add_trace(go.Scatter(
        x=df_focus['day_index'], 
        y=df_focus['streams_cumul'],
        name="Streams Cumulés",
        mode='lines+markers',
        line=dict(color='#1DB954', width=3),
        fill='tozeroy' # Effet remplissage sympa
    ), secondary_y=False)

    # 2. Courbe Popularité
    fig.add_trace(go.Scatter(
        x=df_focus['day_index'], 
        y=df_focus['popularity'],
        name="Index Popularité",
        mode='lines',
        line=dict(color='#ffffff', width=2, dash='dot')
    ), secondary_y=True)

    # 3. Lignes de Seuils (Thresholds)
    # Seuil Release Radar
    fig.add_hline(y=GOAL_RR_STREAMS, line_dash="dash", line_color="orange", annotation_text="Seuil Release Radar (1k)", secondary_y=False)
    # Seuil Discover Weekly
    fig.add_hline(y=GOAL_DW_STREAMS, line_dash="dash", line_color="cyan", annotation_text="Seuil DW (10k)", secondary_y=False)

    fig.update_layout(
        title=f"Trajectoire de '{selected_track}' (28 premiers jours)",
        xaxis_title="Jours depuis la sortie (J+)",
        hovermode="x unified",
        height=600,
        legend=dict(orientation="h", y=1.1)
    )
    
    fig.update_yaxes(title_text="Volume Streams", secondary_y=False)
    fig.update_yaxes(title_text="Popularité (0-100)", secondary_y=True, range=[0, 100])

    st.plotly_chart(fig, width='stretch')
    
    # --- INTELLIGENCE (PREDICTION SIMPLE) ---
    # C'est ici qu'on mettrait le ML plus tard
    if 5 <= days_elapsed < 28:
        avg_daily = current_total / days_elapsed
        projected_28 = avg_daily * 28
        st.info(f"🔮 **Projection :** À ce rythme, vous finirez les 28 jours avec environ **{projected_28:,.0f} streams**.")
        
        if projected_28 > GOAL_DW_STREAMS:
            st.success("🌟 Vous êtes en bonne voie pour le Discover Weekly !")
        elif projected_28 > GOAL_RR_STREAMS:
            st.warning("⚠️ Release Radar probable, mais Discover Weekly hors de portée sans boost.")
        else:
            st.error("📉 Trajectoire insuffisante pour les algos majeurs.")

    db.close()