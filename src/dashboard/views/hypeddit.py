"""Page Hypeddit - Saisie Manuelle & Analyse Globale (Multi-Axes)."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from src.dashboard.utils import get_db_connection
from src.dashboard.utils.i18n import t
from src.dashboard.utils.period_filter import smart_period_filter
from src.dashboard.auth import get_artist_id, is_admin

# --- FONCTION DE CALLBACK POUR LE RESET ---
def clear_form_data():
    """Réinitialise les valeurs du formulaire dans le session state."""
    st.session_state["h_visits"] = 0
    st.session_state["h_clicks"] = 0
    if "h_new_camp_name" in st.session_state:
        st.session_state["h_new_camp_name"] = ""


def add_campaign_stats(campaign_name: str, date, visits: int, clicks: int):
    """Ajoute ou met à jour les statistiques d'une campagne.

    Le budget n'est plus saisi côté Hypeddit : la dépense publicitaire réelle est
    celle de Meta Ads (ROI Breakeven). La colonne DB `budget` reste à sa valeur par
    défaut (0). Seules les visites/clics (vraies métriques smart-link) sont saisies.
    """
    db = get_db_connection()
    artist_id = get_artist_id()
    if artist_id is None:
        if not is_admin():
            return False, t("hypeddit.invalid_session", "❌ Session invalide.")
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
            'clicks': clicks
        }]

        db.upsert_many(
            table='hypeddit_daily_stats',
            data=stats_data,
            conflict_columns=['artist_id', 'campaign_name', 'date'],
            update_columns=['visits', 'clicks', 'updated_at']
        )

        db.close()
        return True, t("hypeddit.save_success", "✅ Données enregistrées avec succès")

    except Exception as e:
        if db:
            db.close()
        return False, t("hypeddit.save_error", "❌ Erreur: {err}").format(err=e)


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
        SELECT campaign_name, date, visits, clicks
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
    st.header(t("hypeddit.global_stats", "📊 Statistiques globales"))

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
        st.info(t("hypeddit.no_data_period", "📭 Aucune donnée trouvée pour la période sélectionnée."))
        return

    # Nettoyage et conversion
    df['visits'] = pd.to_numeric(df['visits'], errors='coerce').fillna(0)
    df['clicks'] = pd.to_numeric(df['clicks'], errors='coerce').fillna(0)
    df['date'] = pd.to_datetime(df['date'])

    # KPIs Moyens — visites/clics seulement (le budget « Hypeddit » était en fait la
    # dépense Meta Ads, retiré de toute la vue ; voir ROI Breakeven pour la dépense pub).
    st.subheader(t("hypeddit.daily_averages", "Moyennes Journalières (Toutes campagnes)"))
    k1, k2 = st.columns(2)
    k1.metric(t("hypeddit.kpi_avg_visits", "👁️ Visites Moy."), f"{int(df['visits'].mean()):,}")
    k2.metric(t("hypeddit.kpi_avg_clicks", "🖱️ Clicks Moy."), f"{int(df['clicks'].mean()):,}")

    st.markdown("---")

    # Graphique Combiné (visites & clics)
    st.subheader(t("hypeddit.global_performance", "📈 Performance Globale"))

    df_agg = df.groupby('date')[['visits', 'clicks']].sum().reset_index()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_agg['date'], y=df_agg['visits'],
        name=t("hypeddit.visits", "Visites"), marker_color='rgba(135, 206, 250, 0.5)', yaxis='y'
    ))
    fig.add_trace(go.Scatter(
        x=df_agg['date'], y=df_agg['clicks'],
        name='Clicks', mode='lines+markers', line=dict(color='#2ECC71', width=2), yaxis='y'
    ))

    fig.update_layout(
        title=t("hypeddit.chart_title", "Visites & Clicks"),
        xaxis=dict(title=t("common.date", "Date")),
        yaxis=dict(title=t("hypeddit.volume_axis", "Volume"), side='left', showgrid=True),
        margin=dict(r=20),
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
        height=550
    )
    st.plotly_chart(fig, width="stretch")

    with st.expander(t("hypeddit.data_detail", "Voir le détail des données")):
        st.dataframe(df, width="stretch")


def _render_history():
    """Section Historique (50 dernières lignes)."""
    st.header(t("hypeddit.history_header", "📋 Historique"))
    db = get_db_connection()
    artist_id = get_artist_id()
    if artist_id is None:
        if not is_admin():
            st.error(t("hypeddit.session_invalid", "Session invalide.")); st.stop()
        artist_id = 1  # admin: defaults to artist 1
    df_hist = db.fetch_df("""
        SELECT campaign_name, date, visits, clicks
        FROM hypeddit_daily_stats
        WHERE artist_id = %s
        ORDER BY date DESC LIMIT 50
    """, (artist_id,))
    db.close()

    if not df_hist.empty:
        df_hist['date'] = pd.to_datetime(df_hist['date']).dt.strftime('%d/%m/%Y')
        st.dataframe(df_hist, width="stretch")
    else:
        st.info(t("hypeddit.empty_history", "Historique vide."))


def _render_entry_form():
    """Section Saisie manuelle — placée en bas de page."""
    st.header(t("hypeddit.entry_header", "📝 Saisir les données"))

    with st.form("hypeddit_entry_form"):
        col1, col2 = st.columns(2)

        with col1:
            existing_campaigns = get_campaigns_list()
            _existing_lbl = t("hypeddit.type_existing", "Existante")
            _new_lbl = t("hypeddit.type_new", "Nouvelle")
            campaign_type = st.radio(t("hypeddit.type_label", "Type"), [_existing_lbl, _new_lbl], horizontal=True)

            if campaign_type == _existing_lbl and existing_campaigns:
                campaign_name = st.selectbox(t("hypeddit.campaign", "🎯 Campagne"), options=existing_campaigns)
            else:
                campaign_name = st.text_input(t("hypeddit.campaign_name", "🎯 Nom de la campagne"), key="h_new_camp_name")

            entry_date = st.date_input(t("hypeddit.date", "📅 Date"), value=datetime.now().date() - timedelta(days=1))

        with col2:
            visits = st.number_input(t("hypeddit.visits_input", "👁️ Visites"), min_value=0, step=1, key="h_visits")
            clicks = st.number_input(t("hypeddit.clicks_input", "🖱️ Clicks"), min_value=0, step=1, key="h_clicks")

        st.markdown("---")

        c1, c2, c3 = st.columns([2, 1, 1])
        with c2:
            submit = st.form_submit_button(t("hypeddit.save_btn", "💾 Enregistrer"), type="primary")
        with c3:
            # Reset button — side effect via on_click callback; return value unused
            st.form_submit_button(t("hypeddit.reset_btn", "🔄 Réinitialiser"), on_click=clear_form_data)

    if submit:
        if not campaign_name:
            st.error(t("hypeddit.campaign_name_required", "Nom de campagne requis"))
        else:
            success, msg = add_campaign_stats(campaign_name, entry_date, visits, clicks)
            if success:
                st.success(msg)
            else:
                st.error(msg)


def show():
    st.title(t("hypeddit.title", "📱 Hypeddit - Gestion & Analyse"))
    st.markdown("---")

    # Single scrolling page: stats first, history next, manual entry last.
    _render_global_stats()
    st.markdown("---")
    _render_history()
    st.markdown("---")
    _render_entry_form()

if __name__ == "__main__":
    show()
