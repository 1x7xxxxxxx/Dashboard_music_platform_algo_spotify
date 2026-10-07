"""SACEM royalties — a SECTION of the distributors page since R461.

Type: Sub
Uses: i18n, charts, credentials.router.goto_tab
Triggers: called by views.imusician.show() (R461 — owner, 2026-10-07: « fusionne les
          deux en un … Distributeur iMusician DistroKid + SACEM »). `?page=sacem` is an
          alias of `imusician` (routes.PAGE_ALIASES).
Persists in: — (reads sacem_statement, written by the SACEM xlsx import)

Free-tier. Shows the SACEM account statement: gross royalties (REPARTITION lines),
social charges (CSG/CRDS/URSSAF), the net actually paid and the bank transfers to
date, plus a chart of royalty income over time. The gross royalties also feed the
ROI Breakeven (kpi_helpers.get_roi_data).

Neither total is computed here: gross comes from `v_sacem_monthly` (migration 111),
net from `v_artist_monthly_revenue_net` (migration 115). The netting rule — which
line kinds are subtracted, and from what base — is a business rule, and it lived in
this file until 2026-09-14 while being wrong by 41 %.
"""
import pandas as pd
import streamlit as st

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


def _load_net(db, artist_id) -> tuple[float, float]:
    """`(retenues, net)` — `v_artist_monthly_revenue_net` (migration 115).

    Le net NE se calcule pas ici. Il valait `gross + charges + tva` jusqu'au
    2026-09-14, et cette ligne — une règle métier écrite dans une surface — affichait
    **21,49 €** à un artiste qui avait reçu **36,49 €** sur son compte : elle
    retranchait des royalties la TVA d'un frais d'adhésion payé en 2023, un an avant
    la première répartition. La règle vit en SQL, avec sa justification.
    """
    row = db.fetch_query(
        "SELECT COALESCE(SUM(deductions_eur), 0), COALESCE(SUM(net_eur), 0) "
        "FROM v_artist_monthly_revenue_net "
        "WHERE artist_id = %s AND source = 'sacem'",
        (artist_id,))
    if not row:
        return 0.0, 0.0
    return float(row[0][0] or 0), float(row[0][1] or 0)


def gross_to_net_figure(gross: float, deductions: float, net: float):
    """Brut → retenues → net, as a waterfall (R389). Pure.

    The net bar is ABSOLUTE, not plotly's computed total: the net comes from its own
    view (`_load_net`), and a computed total would draw `gross − deductions` even on
    the day the two disagree — hiding the very gap the caption below names."""
    import plotly.graph_objects as go

    labels = [t("sacem.kpi_gross", "💰 Royalties brutes"),
              t("sacem.deductions", "🧾 Retenues"),
              t("sacem.kpi_net", "✅ Net versé")]
    values = [gross, -abs(deductions), net]
    fig = go.Figure(go.Waterfall(
        x=labels, y=values, measure=["absolute", "relative", "absolute"],
        text=[f"{v:,.2f} €" for v in values], textposition="outside",
        hovertemplate="%{x}<br>%{y:,.2f} €<extra></extra>"))
    fig.update_layout(title=t("sacem.waterfall_title", "Du brut au net versé"),
                      yaxis_title="€", height=380, showlegend=False)
    return fig


def render_section(db, artist_id) -> None:
    """The SACEM block, on the page and connection of its caller (rule 9: one per view)."""
    st.subheader(t("sacem.title", "🎼 Royalties SACEM"))
    st.caption(t("sacem.caption",
                 "Relevé de compte SACEM : royalties brutes (REPARTITION), charges "
                 "sociales, net réellement versé et virements reçus à ce jour. "
                 "Les royalties brutes alimentent le ROI Breakheaven."))

    with st.expander(t("sacem.howto_header", "📥 Comment obtenir votre relevé SACEM")):
        st.markdown(t("sacem.howto_body",
                      "1. Connectez-vous sur **sacem.fr** (espace membre).\n"
                      "2. **Mes répartitions** → **Relevé de compte**.\n"
                      "3. Réglez le filtre de **date sur « depuis l'inscription »** (pour tout "
                      "l'historique).\n"
                      "4. **Téléchargez le fichier `.xlsx`**.\n"
                      "5. Importez-le dans l'onglet **📂 Ajouter mes chiffres** des Credentials "
                      "(le type SACEM est détecté automatiquement)."))

    # R389 (V80) : le relevé est un .xlsx, pas un CSV — l'artiste cherchait un CSV que
    # la SACEM ne fournit pas. Et le bouton mène à l'ONGLET d'import, pas à la page.
    st.caption(t("sacem.xlsx_note",
                 "Le relevé SACEM est un fichier **Excel (.xlsx)**, pas un CSV : "
                 "importe-le tel quel."))
    if st.button(t("sacem.import_btn", "📂 Importer mon relevé SACEM (.xlsx)"),
                 key="sacem_import"):
        from src.dashboard.views.credentials.router import CSV_TAB_KEY, goto_tab
        goto_tab(CSV_TAB_KEY)

    df = _load(db, artist_id)
    if df.empty:
        st.info(t("sacem.no_data",
                  "Aucune donnée SACEM. Importe ton relevé de compte (.xlsx) avec le "
                  "bouton ci-dessus."))
        return

    df['mouvement_eur'] = pd.to_numeric(df['mouvement_eur'], errors='coerce').fillna(0.0)
    totals = _load_totals(db, artist_id)
    gross = totals.get('repartition', 0.0)
    deductions, net = _load_net(db, artist_id)

    # R389 (V79) : trois tuiles devenues UN graphique — du brut au net, la retenue
    # entre les deux se lit comme une marche, pas comme une soustraction à faire.
    from src.dashboard.utils import charts
    charts.plotly_chart(gross_to_net_figure(gross, deductions, net), width="stretch")

    # Les DEUX chiffres, et ce qui les sépare (R107 §2, tranché le 2026-09-14).
    # Un artiste qui ne lit que le brut découvre l'écart à son relevé bancaire ;
    # qui ne lit que le net ne peut plus se comparer au brut distributeur.
    st.caption(t("sacem.gross_net_caption",
                 "Brut {gross:,.2f} € − retenues {deductions:,.2f} € = "
                 "**net {net:,.2f} €**. Les retenues sont les charges sociales "
                 "(CSG, CRDS, URSSAF, formation) et la TVA forfaitaire prélevées "
                 "sur chaque répartition. Les frais d'adhésion, eux, n'en sont "
                 "pas : ils ne se retranchent d'aucune royaltie.")
               .format(gross=gross, deductions=abs(deductions), net=net))

    payout = -totals.get('payout', 0.0)
    if payout:
        # Le seul chiffre qu'un artiste peut vérifier sur son relevé bancaire.
        # L'écart avec le net est la part distribuée pas encore virée — un fait
        # du calendrier SACEM, jamais une erreur, donc il se DIT.
        pending = net - payout
        st.caption(t("sacem.payout_caption",
                     "🏦 Déjà viré sur votre compte : **{payout:,.2f} €**"
                     "{pending}.")
                   .format(payout=payout,
                           pending=(
                               t("sacem.payout_pending",
                                 " — reste {p:,.2f} € distribués, en attente du "
                                 "prochain virement trimestriel").format(p=pending)
                               if round(pending, 2) > 0 else "")))

    # ── The treasury (R212) ──
    # The quarterly royalty chart merged into the ONE treasury figure the owner asked
    # for: SACEM (net) beside sales and every spend, from `v_artist_monthly_cashflow`.
    # The gross figures above and the full ledger below stay.
    # R244 (fiche 19 « fusionner ») : the treasury is drawn ONCE, on the distributors
    # page, SACEM included — the same figure here was the owner's « déjà vu ».
    st.caption(t("sacem.treasury_moved",
                 "💶 Ta SACEM entre aussi dans la trésorerie cumulée (ventes, SACEM, "
                 "dépenses) plus haut sur cette page."))

    # ── Full ledger ──
    with st.expander(t("sacem.ledger", "▸ Relevé détaillé")):
        view = df.rename(columns={
            'line_date': t("sacem.col_date", "Date"),
            'libelle': t("sacem.col_label", "Libellé"),
            'mouvement_eur': t("sacem.col_movement", "Mouvement (€)"),
            'solde_eur': t("sacem.col_balance", "Solde (€)"),
            'line_type': t("sacem.col_type", "Type")})
        st.dataframe(view, hide_index=True, width="stretch")
