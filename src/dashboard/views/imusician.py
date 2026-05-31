"""Vue iMusician — saisie manuelle des revenus mensuels, visualisation, ROI Breakheaven."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.ui import smart_date_range
from src.dashboard.auth import get_artist_id, is_admin
from src.dashboard.utils.kpi_helpers import get_roi_data, get_monthly_roi_series


def _roi_data_span(db, artist_id):
    """Return (min_date, max_date) spanning iMusician revenue + Meta spend, or (None, None).

    The ROI filter is bounded to this so the default window always contains data —
    a fixed "last 6 months" returned zero because Meta spend is historical.
    """
    if artist_id is not None:
        rows = db.fetch_query(
            """SELECT MIN(d), MAX(d) FROM (
                   SELECT make_date(year, month, 1) AS d FROM imusician_monthly_revenue WHERE artist_id = %s
                   UNION ALL
                   SELECT day_date::date FROM meta_insights_performance_day WHERE artist_id = %s
               ) t""",
            (artist_id, artist_id),
        )
    else:
        rows = db.fetch_query(
            """SELECT MIN(d), MAX(d) FROM (
                   SELECT make_date(year, month, 1) AS d FROM imusician_monthly_revenue
                   UNION ALL
                   SELECT day_date::date FROM meta_insights_performance_day
               ) t"""
        )
    if rows and rows[0][0]:
        return rows[0][0], rows[0][1]
    return None, None


MONTHS_FR = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
    5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
    9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
}


def _get_artist_filter():
    """Retourne (artist_id, label) selon le rôle courant."""
    if is_admin():
        return None, "Tous les artistes"
    aid = get_artist_id()
    return aid, f"Artiste {aid}"


def _load_revenues(db, artist_id):
    """Charge les revenus depuis la DB."""
    if artist_id is None:
        query = """
            SELECT r.year, r.month, r.revenue_eur, r.notes, s.name AS artist_name
            FROM imusician_monthly_revenue r
            JOIN saas_artists s ON s.id = r.artist_id
            ORDER BY r.year DESC, r.month DESC
        """
        return db.fetch_df(query)
    else:
        query = """
            SELECT year, month, revenue_eur, notes
            FROM imusician_monthly_revenue
            WHERE artist_id = %s
            ORDER BY year DESC, month DESC
        """
        return db.fetch_df(query, (artist_id,))


def _delete_revenue(db, artist_id, year, month):
    """Supprime un enregistrement de revenu."""
    db.execute_query(
        "DELETE FROM imusician_monthly_revenue WHERE artist_id = %s AND year = %s AND month = %s",
        (artist_id, year, month)
    )


def show():
    st.title("💰 Distributeur — Revenus mensuels")
    st.markdown(
        "Visualisation des revenus générés via votre distributeur. "
        "L'import des fichiers iMusician se fait depuis la page **📂 Import CSV**."
    )

    tab_data, tab_roi = st.tabs(["📊 Données", "💹 ROI Breakheaven"])

    db = get_db_connection()
    try:
        artist_id, _ = _get_artist_filter()

        # ── Onglet : Données + graphique ────────────────────────────────────
        with tab_data:
            df = _load_revenues(db, artist_id)

            if df.empty:
                st.info(
                    "Aucun revenu enregistré. Importez un export iMusician "
                    "depuis la page **📂 Import CSV**."
                )
            else:
                # Colonne lisible mois/année
                df['period'] = df.apply(
                    lambda r: f"{MONTHS_FR[int(r['month'])]} {int(r['year'])}", axis=1
                )
                df['date_sort'] = pd.to_datetime(
                    df.apply(lambda r: f"{int(r['year'])}-{int(r['month']):02d}-01", axis=1)
                )

                # ── Filtres année / mois ─────────────────────────────────────
                available_years = sorted(df['year'].astype(int).unique(), reverse=True)
                available_months = sorted(df['month'].astype(int).unique())

                fcol1, fcol2 = st.columns(2)
                with fcol1:
                    selected_years = st.multiselect(
                        "Filtrer par année",
                        options=available_years,
                        default=available_years,
                        format_func=str,
                    )
                with fcol2:
                    selected_months = st.multiselect(
                        "Filtrer par mois",
                        options=available_months,
                        default=available_months,
                        format_func=lambda m: MONTHS_FR[m],
                    )

                if not selected_years or not selected_months:
                    st.warning("Sélectionnez au moins une année et un mois.")
                else:
                    mask = (
                        df['year'].astype(int).isin(selected_years)
                        & df['month'].astype(int).isin(selected_months)
                    )
                    df = df[mask]

                    if df.empty:
                        st.info("Aucune donnée pour cette sélection.")
                    else:
                        df_sorted = df.sort_values('date_sort')

                        # KPI total
                        total = df['revenue_eur'].sum()
                        avg = df['revenue_eur'].mean()
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Total cumulé", f"{total:,.2f} €")
                        col2.metric("Moyenne mensuelle", f"{avg:,.2f} €")
                        col3.metric("Mois renseignés", len(df))

                        st.markdown("---")

                        # Graphique
                        fig = px.bar(
                            df_sorted, x='date_sort', y='revenue_eur',
                            labels={'date_sort': '', 'revenue_eur': 'Revenus (€)'},
                            color_discrete_sequence=['#1DB954'],
                            text='revenue_eur'
                        )
                        fig.update_traces(texttemplate='%{text:.2f} €', textposition='outside')
                        fig.update_layout(
                            xaxis_tickformat='%b %Y',
                            yaxis_title="Revenus (€)",
                            showlegend=False,
                            hovermode="x unified"
                        )
                        st.plotly_chart(fig, width="stretch")

                        st.markdown("---")
                        st.subheader("Détail")

                        # Tableau affiché
                        display_cols = ['period', 'revenue_eur', 'notes']
                        if is_admin() and 'artist_name' in df.columns:
                            display_cols = ['artist_name'] + display_cols
                        st.dataframe(
                            df[display_cols].rename(columns={
                                'artist_name': 'Artiste',
                                'period': 'Période',
                                'revenue_eur': 'Revenus (€)',
                                'notes': 'Notes'
                            }),
                            width="stretch",
                            hide_index=True
                        )

                        # Suppression d'une entrée
                        with st.expander("🗑️ Supprimer une entrée"):
                            del_target_id = artist_id
                            if is_admin():
                                artists_df2 = db.fetch_df(
                                    "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY name"
                                )
                                artist_opts2 = {row['name']: row['id'] for _, row in artists_df2.iterrows()}
                                del_name = st.selectbox("Artiste", list(artist_opts2.keys()), key="del_artist")
                                del_target_id = artist_opts2[del_name]

                            del_year = st.number_input(
                                "Année", min_value=2015, max_value=datetime.now().year + 1,
                                value=datetime.now().year, step=1, key="del_year"
                            )
                            del_month = st.selectbox(
                                "Mois", options=list(MONTHS_FR.keys()),
                                format_func=lambda m: MONTHS_FR[m],
                                index=0, key="del_month"
                            )
                            if st.button("🗑️ Supprimer", type="secondary"):
                                try:
                                    _delete_revenue(db, del_target_id, int(del_year), int(del_month))
                                    st.success(f"Entrée supprimée : {MONTHS_FR[del_month]} {del_year}")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erreur : {e}")

        # ── Onglet : ROI Breakheaven ────────────────────────────────────────
        with tab_roi:
            st.subheader("💹 ROI Breakheaven")
            st.caption("Revenus iMusician vs dépenses Meta Ads sur la période sélectionnée")

            span_min, span_max = _roi_data_span(db, artist_id)
            from_date, to_date = smart_date_range("Période", span_min, span_max, key="imusician_roi")

            if from_date is None:
                st.info(
                    "Aucune donnée de revenus iMusician ni de dépenses Meta Ads pour cet artiste. "
                    "Importez un export iMusician (page Import CSV) et lancez la collecte Meta "
                    "depuis l'accueil."
                )
            else:
                roi = get_roi_data(db, artist_id, from_date, to_date)

                c1, c2, c3 = st.columns(3)
                c1.metric("💰 Revenus iMusician", f"{roi['revenue_eur']:,.2f} €")
                c2.metric("📱 Dépenses Meta", f"{roi['meta_spend']:,.2f} €")

                if roi['roi_pct'] is not None:
                    roi_label = f"{roi['roi_pct']:.1f} %"
                    roi_delta = "✅ Rentable" if roi['profitable'] else "⚠️ Déficitaire"
                    c3.metric(
                        "📊 ROI", roi_label, roi_delta,
                        delta_color="normal" if roi['profitable'] else "inverse"
                    )
                else:
                    c3.metric("📊 ROI", "—", help="Aucune dépense Meta sur la période — élargissez le filtre")

                df_series = get_monthly_roi_series(db, artist_id, from_date, to_date)
                if not df_series.empty:
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=df_series['period_date'], y=df_series['revenue_eur'],
                        name="Revenus (€)", marker_color="#1DB954"
                    ))
                    fig.add_trace(go.Bar(
                        x=df_series['period_date'], y=df_series['meta_spend'],
                        name="Dépenses Meta (€)", marker_color="#FF4444"
                    ))
                    fig.update_layout(
                        barmode='group',
                        xaxis_tickformat='%b %Y',
                        yaxis_title="Euros (€)",
                        hovermode="x unified",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig, width="stretch")
                else:
                    st.info("Aucune donnée de revenus ou dépenses sur cette période.")

    finally:
        db.close()
