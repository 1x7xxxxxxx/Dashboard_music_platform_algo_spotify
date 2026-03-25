"""Page Hypeddit - Saisie Manuelle & Analyse Globale (Multi-Axes)."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id

# --- FONCTION DE CALLBACK POUR LE RESET ---
def clear_form_data():
    """Réinitialise les valeurs du formulaire dans le session state."""
    st.session_state["h_visits"] = 0
    st.session_state["h_clicks"] = 0
    st.session_state["h_budget"] = 0.0
    if "h_new_camp_name" in st.session_state:
        st.session_state["h_new_camp_name"] = ""


def add_campaign_stats(campaign_name: str, date, visits: int, clicks: int, budget: float):
    """Ajoute ou met à jour les statistiques d'une campagne."""
    db = get_db_connection()
    
    try:
        # 1. Assurer que la campagne existe
        campaign_data = [{
            'artist_id': get_artist_id() or 1,
            'campaign_name': campaign_name,
            'is_active': True
        }]

        db.upsert_many(
            table='hypeddit_campaigns',
            data=campaign_data,
            conflict_columns=['artist_id', 'campaign_name'],
            update_columns=['is_active', 'updated_at']
        )

        # 2. Stats
        stats_data = [{
            'artist_id': get_artist_id() or 1,
            'campaign_name': campaign_name,
            'date': date,
            'visits': visits,
            'clicks': clicks,
            'budget': budget
        }]

        db.upsert_many(
            table='hypeddit_daily_stats',
            data=stats_data,
            conflict_columns=['artist_id', 'campaign_name', 'date'],
            update_columns=['visits', 'clicks', 'budget', 'updated_at']
        )

        db.close()
        return True, "✅ Données enregistrées avec succès"

    except Exception as e:
        if db:
            db.close()
        return False, f"❌ Erreur: {str(e)}"


def get_campaigns_list():
    db = get_db_connection()
    artist_id = get_artist_id() or 1
    query = "SELECT campaign_name FROM hypeddit_campaigns WHERE is_active = true AND artist_id = %s ORDER BY created_at DESC"
    df = db.fetch_df(query, (artist_id,))
    db.close()
    return df['campaign_name'].tolist() if not df.empty else []


def get_global_stats(start_date, end_date):
    """Récupère les statistiques de TOUTES les campagnes sur la période."""
    db = get_db_connection()
    artist_id = get_artist_id() or 1
    query = """
        SELECT campaign_name, date, visits, clicks, budget, ctr, cost_per_click
        FROM hypeddit_daily_stats
        WHERE date >= %s AND date <= %s AND artist_id = %s
        ORDER BY date
    """
    df = db.fetch_df(query, (start_date, end_date, artist_id))
    db.close()
    return df


def show():
    st.title("📱 Hypeddit - Gestion & Analyse")
    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs(["📝 Saisie", "📊 Statistiques Globales", "📋 Historique"])
    
    # ============================================================================
    # ONGLET 1 : SAISIE
    # ============================================================================
    with tab1:
        st.header("📝 Saisir les données")
        
        with st.form("hypeddit_entry_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                existing_campaigns = get_campaigns_list()
                campaign_type = st.radio("Type", ["Existante", "Nouvelle"], horizontal=True)
                
                if campaign_type == "Existante" and existing_campaigns:
                    campaign_name = st.selectbox("🎯 Campagne", options=existing_campaigns)
                else:
                    campaign_name = st.text_input("🎯 Nom de la campagne", key="h_new_camp_name")
                
                entry_date = st.date_input("📅 Date", value=datetime.now().date() - timedelta(days=1))
            
            with col2:
                visits = st.number_input("👁️ Visites", min_value=0, step=1, key="h_visits")
                clicks = st.number_input("🖱️ Clicks", min_value=0, step=1, key="h_clicks")
                budget = st.number_input("💰 Budget (€)", min_value=0.0, step=0.01, format="%.2f", key="h_budget")
            
            st.markdown("---")
            
            c1, c2, c3 = st.columns([2, 1, 1])
            with c2:
                submit = st.form_submit_button("💾 Enregistrer", type="primary")
            with c3:
                clear = st.form_submit_button("🔄 Réinitialiser", on_click=clear_form_data)
        
        if submit:
            if not campaign_name:
                st.error("Nom de campagne requis")
            else:
                success, msg = add_campaign_stats(campaign_name, entry_date, visits, clicks, budget)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)

    # ============================================================================
    # ONGLET 2 : STATS GLOBALES
    # ============================================================================
    with tab2:
        st.header("📊 Analyse de l'année en cours")
        
        col1, col2 = st.columns(2)
        current_year = datetime.now().year
        
        with col1:
            start = st.date_input("📅 Début", value=datetime(current_year, 1, 1), key="d1")
        with col2:
            end = st.date_input("📅 Fin", value=datetime.now(), key="d2")
            
        st.markdown("---")
        
        df = get_global_stats(start, end)
        
        if not df.empty:
            # Nettoyage et conversion
            df['visits'] = pd.to_numeric(df['visits'], errors='coerce').fillna(0)
            df['clicks'] = pd.to_numeric(df['clicks'], errors='coerce').fillna(0)
            df['budget'] = pd.to_numeric(df['budget'], errors='coerce').fillna(0)
            df['cost_per_click'] = pd.to_numeric(df['cost_per_click'], errors='coerce').fillna(0)
            df['date'] = pd.to_datetime(df['date'])
            
            # KPIs Moyens
            st.subheader("Moyennes Journalières (Toutes campagnes)")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("👁️ Visites Moy.", f"{int(df['visits'].mean()):,}")
            k2.metric("🖱️ Clicks Moy.", f"{int(df['clicks'].mean()):,}")
            k3.metric("💰 Budget Moy.", f"{df['budget'].mean():.2f} €")
            k4.metric("📉 CPC Moy.", f"{df['cost_per_click'].mean():.2f} €")
            
            st.markdown("---")
            
            # 3. Graphique Combiné (4 indicateurs)
            st.subheader("📈 Performance Globale")
            
            # Aggrégation par date
            # Pour le CPC, on doit recalculer la moyenne pondérée (Total Budget / Total Clicks) pour être précis
            df_agg = df.groupby('date')[['visits', 'clicks', 'budget']].sum().reset_index()
            df_agg['cpc'] = df_agg.apply(lambda x: x['budget'] / x['clicks'] if x['clicks'] > 0 else 0, axis=1)
            
            fig = go.Figure()
            
            # Axe Y1 (Gauche) : Visites
            fig.add_trace(go.Bar(
                x=df_agg['date'], y=df_agg['visits'],
                name='Visites',
                marker_color='rgba(135, 206, 250, 0.5)',
                yaxis='y'
            ))
            
            # Axe Y1 (Gauche) : Clicks
            fig.add_trace(go.Scatter(
                x=df_agg['date'], y=df_agg['clicks'],
                name='Clicks',
                mode='lines+markers',
                line=dict(color='#2ECC71', width=2),
                yaxis='y'
            ))
            
            # Axe Y2 (Droite 1) : Budget
            fig.add_trace(go.Scatter(
                x=df_agg['date'], y=df_agg['budget'],
                name='Budget (€)',
                mode='lines',
                line=dict(color='#E74C3C', width=2, dash='dot'),
                yaxis='y2'
            ))
            
            # Axe Y3 (Droite 2 - Décalée) : CPC
            fig.add_trace(go.Scatter(
                x=df_agg['date'], y=df_agg['cpc'],
                name='CPC (€)',
                mode='lines+markers',
                line=dict(color='#9B59B6', width=2), # Violet
                yaxis='y3'
            ))
            
            fig.update_layout(
                title="Visites & Clicks vs Budget & CPC",
                xaxis=dict(title="Date"),
                
                # Axe Gauche (Visites/Clicks)
                yaxis=dict(
                    title="Volume",
                    side='left',
                    showgrid=True
                ),
                
                # Axe Droite 1 (Budget)
                yaxis2=dict(
                    title="Budget (€)",
                    titlefont=dict(color="#E74C3C"),
                    tickfont=dict(color="#E74C3C"),
                    anchor="x",
                    overlaying="y",
                    side="right"
                ),
                
                # Axe Droite 2 (CPC) - Décalé pour ne pas chevaucher
                yaxis3=dict(
                    title="CPC (€)",
                    titlefont=dict(color="#9B59B6"),
                    tickfont=dict(color="#9B59B6"),
                    anchor="free",
                    overlaying="y",
                    side="right",
                    position=1.0, # Positionne l'axe un peu plus à droite
                    showgrid=False
                ),
                
                # Ajustement des marges pour faire place au 3ème axe
                margin=dict(r=20), # Marge droite
                hovermode='x unified',
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.05,
                    xanchor="right",
                    x=1
                ),
                height=550
            )

            st.plotly_chart(fig, width="stretch")

            with st.expander("Voir le détail des données"):
                st.dataframe(df, width="stretch")
            
        else:
            st.info("📭 Aucune donnée trouvée pour la période sélectionnée.")

    # ============================================================================
    # ONGLET 3 : HISTORIQUE
    # ============================================================================
    with tab3:
        db = get_db_connection()
        artist_id = get_artist_id() or 1
        df_hist = db.fetch_df("""
            SELECT campaign_name, date, visits, clicks, budget, ctr, cost_per_click
            FROM hypeddit_daily_stats
            WHERE artist_id = %s
            ORDER BY date DESC LIMIT 50
        """, (artist_id,))
        db.close()
        
        if not df_hist.empty:
            df_hist['date'] = pd.to_datetime(df_hist['date']).dt.strftime('%d/%m/%Y')
            st.dataframe(df_hist, width="stretch")
        else:
            st.info("Historique vide.")

if __name__ == "__main__":
    show()