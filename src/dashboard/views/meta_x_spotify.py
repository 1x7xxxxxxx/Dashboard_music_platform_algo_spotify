import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from src.dashboard.utils import get_db_connection

def show():
    st.title("🔀 META x SPOTIFY - Analyse ROI")
    st.markdown("---")

    db = get_db_connection()

    # =========================================================================
    # 1. SECTION CONFIGURATION (MAPPING)
    # =========================================================================
    with st.expander("⚙️ Gérer les associations (Campagnes <-> Titres)", expanded=False):
        c1, c2 = st.columns(2)
        
        # Récupération des listes depuis les tables propres
        try:
            df_camps = db.fetch_df("SELECT DISTINCT campaign_name FROM meta_campaigns ORDER BY campaign_name")
            campaigns = df_camps['campaign_name'].tolist()
        except: campaigns = []

        try:
            df_tracks = db.fetch_df("SELECT DISTINCT track_name FROM tracks ORDER BY track_name")
            tracks = df_tracks['track_name'].tolist()
        except: tracks = []

        # Formulaire d'ajout
        with st.form("mapping_form"):
            st.write("Créer un nouveau lien :")
            col_a, col_b = st.columns(2)
            sel_camp = col_a.selectbox("Campagne Meta Ads", campaigns)
            sel_track = col_b.selectbox("Titre Spotify", tracks)
            
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

        # Tableau des liens existants
        st.markdown("#### Liens actifs")
        try:
            curr_map = db.fetch_df("SELECT campaign_name, track_name, created_at FROM campaign_track_mapping ORDER BY created_at DESC")
            if not curr_map.empty:
                st.dataframe(curr_map, width='stretch', hide_index=True)
                
                col_del, _ = st.columns([1, 4])
                if col_del.button("🗑️ Réinitialiser tous les liens"):
                    with db.conn.cursor() as cur:
                        cur.execute("TRUNCATE TABLE campaign_track_mapping")
                        db.conn.commit()
                    st.rerun()
            else:
                st.info("Aucun lien configuré. Utilisez le formulaire ci-dessus.")
        except: pass

    # =========================================================================
    # 2. SECTION ANALYSE (VISUALISATION)
    # =========================================================================
    st.header("📊 Performance & ROI")

    # Sélecteur de Mode (Détail vs Global)
    view_mode = st.radio(
        "Mode d'analyse :", 
        ["🎯 Par Campagne (Vue détaillée)", "💿 Par Titre (Vue agrégée)"], 
        horizontal=True
    )

    data = pd.DataFrame()
    col_spend_name = ""
    col_stream_name = "organic_streams"
    chart_title = ""

    # --- CHARGEMENT DES DONNÉES SELON LE MODE ---
    if view_mode == "🎯 Par Campagne (Vue détaillée)":
        try:
            # On charge la Vue Détail (view_meta_spotify_roi)
            df = db.fetch_df("SELECT * FROM view_meta_spotify_roi ORDER BY date ASC")
        except: df = pd.DataFrame()

        if not df.empty:
            df['label'] = df['campaign_name'] + " ➡️ " + df['track_name']
            selection = st.selectbox("Sélectionner le couple à analyser :", df['label'].unique())
            
            data = df[df['label'] == selection].copy()
            col_spend_name = 'ad_spend'
            chart_title = selection
        else:
            st.warning("Aucune donnée détaillée trouvée. Avez-vous importé les CSV et configuré le mapping ?")

    else:
        # Mode Global (view_track_global_roi)
        try:
            df = db.fetch_df("SELECT * FROM view_track_global_roi ORDER BY date ASC")
        except: df = pd.DataFrame()

        if not df.empty:
            selection = st.selectbox("Sélectionner le Titre (Toutes campagnes confondues) :", df['track_name'].unique())
            
            data = df[df['track_name'] == selection].copy()
            col_spend_name = 'total_ad_spend'
            chart_title = f"Global : {selection}"
        else:
            st.warning("Aucune donnée globale trouvée.")

    # --- RENDU GRAPHIQUE ET KPIS ---
    if not data.empty and col_spend_name:
        
        # 1. Nettoyage des Types (Vital pour Plotly)
        data['date'] = pd.to_datetime(data['date'])
        cols_to_float = [col_spend_name, 'organic_streams', 'total_link_clicks', 'total_conversions', 'link_clicks', 'conversions']
        
        for c in cols_to_float:
            if c in data.columns:
                data[c] = pd.to_numeric(data[c], errors='coerce').fillna(0).astype(float)

        # 2. Calculs KPI
        total_spend = data[col_spend_name].sum()
        total_streams = data['organic_streams'].sum()
        
        # Gestion Clics/Conversions selon la vue
        clicks_col = 'total_link_clicks' if 'total_link_clicks' in data.columns else 'link_clicks'
        total_clicks = data[clicks_col].sum() if clicks_col in data.columns else 0
        
        # Calculs Ratios
        cps = total_spend / total_streams if total_streams > 0 else 0
        cpc = total_spend / total_clicks if total_clicks > 0 else 0
        
        # 3. Affichage des Métriques
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💰 Budget Période", f"{total_spend:,.2f} €")
        k2.metric("🎧 Streams", f"{int(total_streams):,}")
        k3.metric("🖱️ Clics (Link)", f"{int(total_clicks):,}")
        k4.metric("📉 Coût / Stream", f"{cps:.3f} €", delta_color="inverse")

        st.markdown("---")

        # 4. Graphique Avancé (Double Axe)
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Barres : Dépenses
        fig.add_trace(
            go.Bar(
                x=data['date'], 
                y=data[col_spend_name], 
                name="Dépenses Pub (€)",
                marker_color='rgba(66, 103, 178, 0.6)', # Bleu Meta
                hovertemplate='%{y:.2f} €<extra></extra>'
            ),
            secondary_y=False
        )

        # Ligne : Streams
        fig.add_trace(
            go.Scatter(
                x=data['date'], 
                y=data['organic_streams'], 
                name="Streams Spotify",
                line=dict(color='#1DB954', width=3, shape='spline'), # Vert Spotify
                mode='lines+markers',
                marker=dict(size=6),
                hovertemplate='%{y} streams<extra></extra>'
            ),
            secondary_y=True
        )

        # Mise en page pro
        fig.update_layout(
            title=f"<b>{chart_title}</b>",
            title_x=0.0,
            legend=dict(orientation="h", y=1.1, x=0),
            hovermode="x unified",
            height=500,
            margin=dict(l=20, r=20, t=80, b=20),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
        )

        # Axes
        fig.update_yaxes(title_text="Dépenses (€)", secondary_y=False, showgrid=True, gridcolor='rgba(128,128,128,0.1)')
        fig.update_yaxes(title_text="Nombre de Streams", secondary_y=True, showgrid=False)
        fig.update_xaxes(showgrid=False)

        st.plotly_chart(fig, width='stretch')

        # 5. Tableau de données brutes
        with st.expander("🔎 Voir les données brutes"):
            st.dataframe(
                data.sort_values('date', ascending=False),
                column_config={
                    "date": "Date",
                    col_spend_name: st.column_config.NumberColumn("Dépenses", format="%.2f €"),
                    "organic_streams": st.column_config.NumberColumn("Streams"),
                    clicks_col: st.column_config.NumberColumn("Clics")
                },
                width='stretch',
                hide_index=True
            )

    db.close()

if __name__ == "__main__":
    show()