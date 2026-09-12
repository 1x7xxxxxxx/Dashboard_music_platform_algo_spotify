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
    """Le DÉTAIL du relevé — une ligne par mouvement, pour le tableau du bas.

    Les trois totaux de la page ne se calculent PAS d'ici : ils viennent de
    `_load_totals`. Les sommer en pandas sur ces lignes était la forme que ce
    dépôt a payée sur la tuile « Dépenses » de Meta Ads — aucun `SUM(` dans la
    requête, donc invisible à tout garde SQL.
    """
    return db.fetch_df(
        "SELECT line_date, libelle, mouvement_eur, solde_eur, line_type "
        "FROM sacem_statement WHERE artist_id = %s ORDER BY line_date DESC, id DESC",
        (artist_id,))


def _load_totals(db, artist_id) -> dict[str, float]:
    """{nature de ligne: montant} — `v_sacem_monthly` (migration 111).

    `repartition` est la MÊME définition que la branche sacem de
    `v_artist_monthly_revenue`, qui lit désormais cette vue : le prédicat
    `line_type = 'repartition'` n'est plus écrit deux fois.
    """
    rows = db.fetch_query(
        "SELECT line_type, COALESCE(SUM(amount), 0) FROM v_sacem_monthly "
        "WHERE artist_id = %s GROUP BY line_type",
        (artist_id,))
    return {line_type: float(amount or 0) for line_type, amount in (rows or [])}


def show():
    st.title(t("sacem.title", "🎼 Royalties SACEM"))
    st.caption(t("sacem.caption",
                 "Relevé de compte SACEM : royalties brutes (REPARTITION), charges "
                 "sociales et net. Les royalties brutes alimentent le ROI Breakheaven."))

    with st.expander(t("sacem.howto_header", "📥 Comment obtenir votre relevé SACEM")):
        st.markdown(t("sacem.howto_body",
                      "1. Connectez-vous sur **sacem.fr** (espace membre).\n"
                      "2. **Mes répartitions** → **Relevé de compte**.\n"
                      "3. Réglez le filtre de **date sur « depuis l'inscription »** (pour tout "
                      "l'historique).\n"
                      "4. **Téléchargez le fichier `.xlsx`**.\n"
                      "5. Importez-le depuis **📂 Ajouter mes chiffres Spotify for Artists & Apple** "
                      "(le type SACEM est détecté "
                      "automatiquement)."))

    with view_session() as (db, artist_id):
        df = _load(db, artist_id)
        if df.empty:
            st.info(t("sacem.no_data",
                      "Aucune donnée SACEM. Importez votre relevé de compte (.xlsx) depuis "
                      "**📂 Ajouter mes chiffres Spotify for Artists & Apple**."))
            return

        df['mouvement_eur'] = pd.to_numeric(df['mouvement_eur'], errors='coerce').fillna(0.0)
        totals = _load_totals(db, artist_id)
        gross = totals.get('repartition', 0.0)
        charges = totals.get('charge', 0.0)     # ≤ 0
        tva = totals.get('tva', 0.0)
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
