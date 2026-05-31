"""Page Hypeddit - Saisie Manuelle & Analyse Globale (Multi-Axes)."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from src.dashboard.utils import get_db_connection
from src.dashboard.utils.period_filter import smart_period_filter
from src.dashboard.auth import get_artist_id, is_admin

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
    artist_id = get_artist_id()
    if artist_id is None:
        if not is_admin():
            return False, "❌ Session invalide."
        artist_id = 1  # admin: defaults to artist 1

    try:
        # 1. Assurer que la campagne existe
        campaign_data = [{
            'artist_id': artist_id,
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
            'artist_id': artist_id,
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
    artist_id = get_artist_id()
    if artist_id is None:
        artist_id = 1  # admin: defaults to artist 1
    query = "SELECT campaign_name FROM hypeddit_campaigns WHERE is_active = true AND artist_id = %s ORDER BY created_at DESC"
    df = db.fetch_df(query, (artist_id,))
    db.close()
    return df['campaign_name'].tolist() if not df.empty else []


def get_global_stats(start_date, end_date, db=None):
    """Récupère les statistiques de TOUTES les campagnes sur la période.

    `db` may be passed in to reuse the caller's connection (rule #9 — one
    connection per view); when None, opens and closes its own.
    """
    own_db = db is None
    if own_db:
        db = get_db_connection()
    artist_id = get_artist_id()
    if artist_id is None:
        artist_id = 1  # admin: defaults to artist 1
    query = """
        SELECT campaign_name, date, visits, clicks, budget, ctr, cost_per_click
        FROM hypeddit_daily_stats
        WHERE date >= %s AND date <= %s AND artist_id = %s
        ORDER BY date
    """
    df = db.fetch_df(query, (start_date, end_date, artist_id))
    if own_db:
        db.close()
    return df


def _render_global_stats():
    """Section Statistiques Globales (graphique multi-axes + KPIs)."""
    st.header("📊 Statistiques globales")

    # Smart period filter (presets + auto-default on data span) instead of two
    # manual date inputs. Reuses one connection for span query + data query.
    db = get_db_connection()
    artist_id = get_artist_id()
    if artist_id is None:
        artist_id = 1  # admin: defaults to artist 1
    window = smart_period_filter(
        db,
        table="hypeddit_daily_stats",
        date_column="date",
        artist_id=artist_id,
        key="hyp_stats",
    )

    df = get_global_stats(window.start, window.end, db=db)
    db.close()

    if df.empty:
        st.info("📭 Aucune donnée trouvée pour la période sélectionnée.")
        return

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

    # Graphique Combiné (4 indicateurs)
    st.subheader("📈 Performance Globale")

    # Aggrégation par date — CPC = moyenne pondérée (Total Budget / Total Clicks)
    df_agg = df.groupby('date')[['visits', 'clicks', 'budget']].sum().reset_index()
    df_agg['cpc'] = df_agg.apply(lambda x: x['budget'] / x['clicks'] if x['clicks'] > 0 else 0, axis=1)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_agg['date'], y=df_agg['visits'],
        name='Visites', marker_color='rgba(135, 206, 250, 0.5)', yaxis='y'
    ))
    fig.add_trace(go.Scatter(
        x=df_agg['date'], y=df_agg['clicks'],
        name='Clicks', mode='lines+markers', line=dict(color='#2ECC71', width=2), yaxis='y'
    ))
    fig.add_trace(go.Scatter(
        x=df_agg['date'], y=df_agg['budget'],
        name='Budget (€)', mode='lines', line=dict(color='#E74C3C', width=2, dash='dot'), yaxis='y2'
    ))
    fig.add_trace(go.Scatter(
        x=df_agg['date'], y=df_agg['cpc'],
        name='CPC (€)', mode='lines+markers', line=dict(color='#9B59B6', width=2), yaxis='y3'
    ))

    fig.update_layout(
        title="Visites & Clicks vs Budget & CPC",
        xaxis=dict(title="Date"),
        yaxis=dict(title="Volume", side='left', showgrid=True),
        yaxis2=dict(
            title=dict(text="Budget (€)", font=dict(color="#E74C3C")),
            tickfont=dict(color="#E74C3C"), anchor="x", overlaying="y", side="right"
        ),
        yaxis3=dict(
            title=dict(text="CPC (€)", font=dict(color="#9B59B6")),
            tickfont=dict(color="#9B59B6"), anchor="free", overlaying="y",
            side="right", position=1.0, showgrid=False
        ),
        margin=dict(r=20),
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
        height=550
    )
    st.plotly_chart(fig, width="stretch")

    with st.expander("Voir le détail des données"):
        st.dataframe(df, width="stretch")


def _render_history():
    """Section Historique (50 dernières lignes)."""
    st.header("📋 Historique")
    db = get_db_connection()
    artist_id = get_artist_id()
    if artist_id is None:
        if not is_admin():
            st.error("Session invalide."); st.stop()
        artist_id = 1  # admin: defaults to artist 1
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


def _render_entry_form():
    """Section Saisie manuelle — placée en bas de page."""
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
            # Reset button — side effect via on_click callback; return value unused
            st.form_submit_button("🔄 Réinitialiser", on_click=clear_form_data)

    if submit:
        if not campaign_name:
            st.error("Nom de campagne requis")
        else:
            success, msg = add_campaign_stats(campaign_name, entry_date, visits, clicks, budget)
            if success:
                st.success(msg)
            else:
                st.error(msg)


def show():
    st.title("📱 Hypeddit - Gestion & Analyse")
    st.markdown("---")

    # Single scrolling page: stats first, history next, manual entry last.
    _render_global_stats()
    st.markdown("---")
    _render_history()
    st.markdown("---")
    _render_entry_form()

if __name__ == "__main__":
    show()
