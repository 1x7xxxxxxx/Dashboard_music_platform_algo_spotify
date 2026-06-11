"""SACEM royalties view — gross distributions, social charges and net over time.

Type: Feature
Uses: view_session, i18n
Persists in: — (reads sacem_statement, written by the SACEM xlsx import)

Free-tier. Shows the SACEM account statement: gross royalties (REPARTITION lines),
social charges (CSG/CRDS/URSSAF), TVA and the net, plus a chart of royalty income
over time. The gross royalties also feed the ROI Breakeven (kpi_helpers.get_roi_data).
"""
import pandas as pd
import streamlit as st

from src.dashboard.utils import view_session
from src.dashboard.utils.i18n import t


def _load(db, artist_id):
    return db.fetch_df(
        "SELECT line_date, libelle, mouvement_eur, solde_eur, line_type "
        "FROM sacem_statement WHERE artist_id = %s ORDER BY line_date DESC, id DESC",
        (artist_id,))


def show():
    st.title(t("sacem.title", "🎼 Royalties SACEM"))
    st.caption(t("sacem.caption",
                 "Relevé de compte SACEM : royalties brutes (REPARTITION), charges "
                 "sociales et net. Les royalties brutes alimentent le ROI Breakheaven."))

    with view_session() as (db, artist_id):
        df = _load(db, artist_id)
        if df.empty:
            st.info(t("sacem.no_data",
                      "Aucune donnée SACEM. Importez votre relevé de compte (.xlsx) depuis "
                      "**📂 Import CSV**."))
            return

        df['mouvement_eur'] = pd.to_numeric(df['mouvement_eur'], errors='coerce').fillna(0.0)
        gross = float(df.loc[df.line_type == 'repartition', 'mouvement_eur'].sum())
        charges = float(df.loc[df.line_type == 'charge', 'mouvement_eur'].sum())   # ≤ 0
        tva = float(df.loc[df.line_type == 'tva', 'mouvement_eur'].sum())
        net = gross + charges + tva

        k1, k2, k3 = st.columns(3)
        k1.metric(t("sacem.kpi_gross", "💰 Royalties brutes"), f"{gross:,.2f} €")
        k2.metric(t("sacem.kpi_charges", "🧾 Charges sociales"), f"{charges:,.2f} €")
        k3.metric(t("sacem.kpi_net", "✅ Net estimé"), f"{net:,.2f} €")

        # ── Royalty income over time (REPARTITION) ──
        rep = df[df.line_type == 'repartition'].sort_values('line_date')
        if not rep.empty:
            import plotly.express as px
            rep = rep.copy()
            rep['date'] = pd.to_datetime(rep['line_date'])
            rep['cumul'] = rep['mouvement_eur'].cumsum()
            st.subheader(t("sacem.chart_header", "📈 Royalties brutes dans le temps"))
            fig = px.bar(rep, x='date', y='mouvement_eur',
                         labels={'mouvement_eur': '€', 'date': ''},
                         title=t("sacem.chart_title", "REPARTITION par trimestre"))
            fig.add_scatter(x=rep['date'], y=rep['cumul'], mode='lines+markers',
                            name=t("sacem.cumul", "Cumulé (€)"))
            st.plotly_chart(fig, width="stretch")

        # ── Full ledger ──
        with st.expander(t("sacem.ledger", "▸ Relevé détaillé")):
            view = df.rename(columns={
                'line_date': t("sacem.col_date", "Date"),
                'libelle': t("sacem.col_label", "Libellé"),
                'mouvement_eur': t("sacem.col_movement", "Mouvement (€)"),
                'solde_eur': t("sacem.col_balance", "Solde (€)"),
                'line_type': t("sacem.col_type", "Type")})
            st.dataframe(view, hide_index=True, width="stretch")
