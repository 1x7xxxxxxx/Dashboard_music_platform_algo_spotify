import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from src.dashboard.utils import get_db_connection

def show():
    st.title("🔀 META x SPOTIFY - Analyse ROI")
    st.markdown("---")

    db = get_db_connection()

    # =========================================================================
    # 1. SECTION CONFIGURATION (MAPPING)
    # =========================================================================
    with st.expander("⚙️ Gérer les associations (Campagnes <-> Titres)", expanded=False):
        try:
            df_camps = db.fetch_df("SELECT DISTINCT campaign_name FROM meta_campaigns ORDER BY campaign_name")
            campaigns = df_camps['campaign_name'].tolist()
        except: campaigns = []

        try:
            df_tracks = db.fetch_df("SELECT DISTINCT track_name FROM tracks ORDER BY track_name")
            tracks = df_tracks['track_name'].tolist()
        except: tracks = []

        with st.form("mapping_form"):
            c1, c2 = st.columns(2)
            sel_camp = c1.selectbox("Campagne Meta Ads", campaigns)
            sel_track = c2.selectbox("Titre Spotify", tracks)
            
            if st.form_submit_button("💾 Enregistrer le lien"):
                if sel_camp and sel_track:
                    try:
                        with db.conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO campaign_track_mapping (campaign_name, track_name)
                                VALUES (%s, %s)
                                ON CONFLICT (campaign_name, track_name) DO NOTHING
                            """, (sel_camp, sel_track))
                            db.conn.commit()
                        st.success(f"✅ Lien activé : {sel_camp} -> {sel_track}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur SQL : {e}")

        try:
            curr_map = db.fetch_df("SELECT campaign_name, track_name, created_at FROM campaign_track_mapping ORDER BY created_at DESC")
            if not curr_map.empty:
                st.dataframe(curr_map, width='stretch', hide_index=True)
        except: pass

    st.markdown("---")

    # =========================================================================
    # 2. ANALYSE CROISÉE (SMART FILTER)
    # =========================================================================
    st.header("📊 Performance 360°")

    try:
        q_camp_list = "SELECT DISTINCT campaign_name FROM meta_insights_performance_day ORDER BY campaign_name DESC"
        camp_list_df = db.fetch_df(q_camp_list)
        available_campaigns = camp_list_df['campaign_name'].tolist()
    except:
        available_campaigns = []

    # --- SÉLECTEUR CAMPAGNE ---
    col_filter, col_date = st.columns([1, 2])
    
    with col_filter:
        selected_campaign = st.selectbox(
            "Choisir la Campagne", 
            options=available_campaigns,
            index=0 if available_campaigns else None
        )

    # --- LOGIQUE INTELLIGENTE DE DATE ---
    default_start = datetime.now().date() - timedelta(days=30)
    default_end = datetime.now().date()

    if selected_campaign:
        try:
            q_start = "SELECT MIN(day_date) as start_date FROM meta_insights_performance_day WHERE campaign_name = %s"
            df_start = db.fetch_df(q_start, (selected_campaign,))
            
            if not df_start.empty and df_start.iloc[0]['start_date']:
                camp_start = pd.to_datetime(df_start.iloc[0]['start_date']).date()
                default_start = camp_start
                default_end = camp_start + timedelta(days=30)
        except Exception: pass

    with col_date:
        date_range = st.date_input(
            "Période d'analyse",
            value=(default_start, default_end),
            format="DD/MM/YYYY"
        )
        
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date, end_date = default_start, default_end

    if not selected_campaign:
        st.info("Sélectionnez une campagne.")
        return

    # --- RÉCUPÉRATION DU TITRE ASSOCIÉ ---
    mapped_track = None
    try:
        res_map = db.fetch_df("SELECT track_name FROM campaign_track_mapping WHERE campaign_name = %s LIMIT 1", (selected_campaign,))
        if not res_map.empty:
            mapped_track = res_map.iloc[0]['track_name']
            st.caption(f"🎵 Titre lié : **{mapped_track}**")
        else:
            st.warning("⚠️ Pas de titre associé. Configurez le lien en haut de page.")
    except: pass

    # =========================================================================
    # 3. RÉCUPÉRATION DES DONNÉES
    # =========================================================================
    
    # A. META ADS
    q_meta = """
        SELECT day_date as date, spend, results, cpr
        FROM meta_insights_performance_day
        WHERE campaign_name = %s AND day_date >= %s AND day_date <= %s
    """
    df_meta = db.fetch_df(q_meta, (selected_campaign, start_date, end_date))

    # B. HYPEDDIT
    q_hypeddit = """
        SELECT date, clicks as hypeddit_clicks, visits as hypeddit_visits
        FROM hypeddit_daily_stats
        WHERE campaign_name = %s AND date >= %s AND date <= %s
    """
    try:
        df_hypeddit = db.fetch_df(q_hypeddit, (selected_campaign, start_date, end_date))
    except:
        df_hypeddit = pd.DataFrame()

    # C. SPOTIFY
    df_spotify = pd.DataFrame()
    if mapped_track:
        try:
            q_streams = """
                SELECT date::date, streams 
                FROM s4a_song_timeline 
                WHERE TRIM(song) = %s AND date >= %s AND date <= %s
                ORDER BY date ASC
            """
            df_streams = db.fetch_df(q_streams, (mapped_track.strip(), start_date, end_date))
        except Exception as e: 
            st.error(f"Erreur Streams SQL: {e}")
            df_streams = pd.DataFrame()

        try:
            q_pop = """
                SELECT date::date, popularity 
                FROM track_popularity_history 
                WHERE TRIM(track_name) = %s AND date >= %s AND date <= %s
            """
            df_pop = db.fetch_df(q_pop, (mapped_track.strip(), start_date, end_date))
        except: df_pop = pd.DataFrame()
        
        if not df_streams.empty:
            df_spotify = df_streams.copy()
            if not df_pop.empty:
                df_spotify['date'] = pd.to_datetime(df_spotify['date'])
                df_pop['date'] = pd.to_datetime(df_pop['date'])
                df_spotify = pd.merge(df_spotify, df_pop, on='date', how='outer')
        elif not df_pop.empty:
            df_spotify = df_pop.copy()

    # =========================================================================
    # 4. FUSION ET NETTOYAGE
    # =========================================================================
    
    all_dates = pd.concat([
        df_meta['date'] if 'date' in df_meta.columns else pd.Series(dtype='object'),
        df_hypeddit['date'] if 'date' in df_hypeddit.columns else pd.Series(dtype='object'),
        df_spotify['date'] if 'date' in df_spotify.columns else pd.Series(dtype='object')
    ]).dropna().unique()

    if len(all_dates) == 0:
        st.warning(f"Aucune donnée trouvée.")
        return

    df_master = pd.DataFrame({'date': sorted(all_dates)})
    df_master['date'] = pd.to_datetime(df_master['date'])

    if not df_meta.empty:
        df_meta['date'] = pd.to_datetime(df_meta['date'])
        df_master = pd.merge(df_master, df_meta, on='date', how='left')
    
    if not df_hypeddit.empty:
        df_hypeddit['date'] = pd.to_datetime(df_hypeddit['date'])
        df_master = pd.merge(df_master, df_hypeddit, on='date', how='left')
        
    if not df_spotify.empty:
        df_spotify['date'] = pd.to_datetime(df_spotify['date'])
        df_master = pd.merge(df_master, df_spotify, on='date', how='left')

    # Force conversion to float
    cols_num = ['spend', 'results', 'cpr', 'hypeddit_clicks', 'hypeddit_visits', 'streams', 'popularity']
    for c in cols_num:
        if c in df_master.columns:
            df_master[c] = pd.to_numeric(df_master[c], errors='coerce').fillna(0).astype(float)

    if 'popularity' in df_master.columns:
        df_master['popularity'] = df_master['popularity'].replace(0, pd.NA).ffill().fillna(0)

    if 'spend' in df_master.columns and 'results' in df_master.columns:
        df_master['cpr_calc'] = df_master.apply(lambda x: x['spend']/x['results'] if x['results'] > 0 else 0.0, axis=1)

    # --- NOUVEAU : CALCUL STREAMS CUMULÉS ---
    if 'streams' in df_master.columns:
        df_master['streams_cumul'] = df_master['streams'].cumsum()
    else:
        df_master['streams_cumul'] = 0.0

    # =========================================================================
    # 5. GRAPHIQUE AVANCÉ
    # =========================================================================
    
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=(
            "💰 Budget (Meta) vs Résultats vs Streams Cumulés", 
            "🌪️ Trafic : Visites Hypeddit vs Clics Sortants", 
            "🎧 Streaming : Streams Journaliers vs Popularité"
        ),
        specs=[
            [{"secondary_y": True}], 
            [{"secondary_y": True}], 
            [{"secondary_y": True}]
        ]
    )

    # --- ROW 1 : META FOCUS (Spend + Results + CPR + STREAMS CUMUL) ---
    
    # 1. Budget (Barres - Axe Y1 Gauche)
    if 'spend' in df_master.columns:
        fig.add_trace(go.Bar(
            x=df_master['date'], y=df_master['spend'],
            name="Budget (€)", marker_color='rgba(255, 99, 97, 0.5)'
        ), row=1, col=1, secondary_y=False)
    
    # 2. Résultats (Ligne - Axe Y2 Droite)
    if 'results' in df_master.columns:
        fig.add_trace(go.Scatter(
            x=df_master['date'], y=df_master['results'],
            name="Résultats (Vol)", mode='lines+markers', line=dict(color='#003f5c', width=3)
        ), row=1, col=1, secondary_y=True)

    # 3. CPR (Pointillés - Axe CUSTOM Y7 Gauche)
    if 'cpr_calc' in df_master.columns:
        fig.add_trace(go.Scatter(
            x=df_master['date'], y=df_master['cpr_calc'],
            name="CPR (€)", mode='lines', 
            line=dict(color='#bc5090', width=2, dash='dot'),
            yaxis='y7' 
        ))

    # 4. STREAMS CUMULÉS (Ligne pleine - Axe CUSTOM Y8 Droite)
    if 'streams_cumul' in df_master.columns:
        fig.add_trace(go.Scatter(
            x=df_master['date'], y=df_master['streams_cumul'],
            name="Streams Cumulés", mode='lines', fill='tozeroy',
            line=dict(color='#117733', width=1), # Vert Foncé
            yaxis='y8'
        ))

    # --- ROW 2 : HYPEDDIT ---
    if 'hypeddit_visits' in df_master.columns:
        fig.add_trace(go.Scatter(
            x=df_master['date'], y=df_master['hypeddit_visits'],
            name="Visites Hypeddit", mode='lines', line=dict(color='#ffa600', width=2)
        ), row=2, col=1, secondary_y=False)

    if 'hypeddit_clicks' in df_master.columns:
        fig.add_trace(go.Bar(
            x=df_master['date'], y=df_master['hypeddit_clicks'],
            name="Clics vers Stores", marker_color='rgba(88, 80, 141, 0.6)'
        ), row=2, col=1, secondary_y=True)

    # --- ROW 3 : SPOTIFY ---
    if 'streams' in df_master.columns:
        fig.add_trace(go.Bar(
            x=df_master['date'], y=df_master['streams'],
            name="Streams Jour", marker_color='rgba(29, 185, 84, 0.7)' # Vert Spotify
        ), row=3, col=1, secondary_y=False)

    if 'popularity' in df_master.columns:
        fig.add_trace(go.Scatter(
            x=df_master['date'], y=df_master['popularity'],
            name="Popularité", mode='lines', line=dict(color='#00D166', width=2) # Vert Fluo
        ), row=3, col=1, secondary_y=True)

    # MISE EN FORME AVANCÉE
    fig.update_layout(
        height=900,
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", y=1.01),
        title_text=f"Analyse Détaillée : {selected_campaign}",
        
        xaxis=dict(type='date'),
        xaxis2=dict(type='date'),
        xaxis3=dict(title="Date", type='date'),

        # AXE SUPPLEMENTAIRE CPR (Gauche)
        yaxis7=dict(
            title="CPR (€)",
            titlefont=dict(color="#bc5090"),
            tickfont=dict(color="#bc5090"),
            anchor="free",
            overlaying="y",
            side="right",
            position=0.05,
            showgrid=False
        ),

        # AXE SUPPLEMENTAIRE STREAMS CUMULÉS (Droite)
        yaxis8=dict(
            title="Cumul Streams",
            titlefont=dict(color="#117733"),
            tickfont=dict(color="#117733"),
            anchor="free",
            overlaying="y",
            side="right",
            position=0.95, # A droite de l'axe Y2
            showgrid=False
        )
    )
    
    fig.update_yaxes(title_text="Budget (€)", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Volume Conv.", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="Visites", row=2, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Clics Sortants", row=2, col=1, secondary_y=True)
    fig.update_yaxes(title_text="Streams Jour", row=3, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Index Pop.", row=3, col=1, secondary_y=True, range=[0, 100])

    st.plotly_chart(fig, width='stretch')

    # --- TABLEAU ---
    with st.expander("🔎 Voir les données brutes"):
        st.dataframe(
            df_master.sort_values('date', ascending=False).style.format({
                "spend": "{:.2f}", "cpr_calc": "{:.2f}", "streams": "{:.0f}", "streams_cumul": "{:.0f}", "popularity": "{:.0f}"
            }), 
            width='stretch'
        )

    db.close()

if __name__ == "__main__":
    show()