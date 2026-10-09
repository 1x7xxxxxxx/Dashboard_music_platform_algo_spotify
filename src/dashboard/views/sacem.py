"""SACEM royalties — a SECTION of the distributors page since R461.

Type: Sub
Uses: i18n, charts, credentials.router.goto_tab
Triggers: called by views.imusician.show() (R461 — owner, 2026-10-07: « fusionne les
          deux en un … Distributeur iMusician DistroKid + SACEM »). `?page=sacem` is an
          alias of `imusician` (routes.PAGE_ALIASES).
Persists in: — (reads sacem_statement, written by the SACEM xlsx import)

Free-tier. Shows the SACEM account statement: gross royalties (REPARTITION lines),
social charges (CSG/CRDS/URSSAF), the net actually paid and the bank transfers to
date — one pie since R488. The gross royalties also feed the break-even of the cross
view's « Revenus » section.

Neither total is computed here: gross comes from `v_sacem_monthly` (migration 111),
net from `v_artist_monthly_revenue_net` (migration 115). The netting rule — which
line kinds are subtracted, and from what base — is a business rule, and it lived in
this file until 2026-09-14 while being wrong by 41 %.
"""
import streamlit as st

from src.dashboard.utils.i18n import t


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


def royalties_split(gross: float, deductions: float, net: float,
                    paid: float) -> list[tuple[str, float]]:
    """Where the gross royalties went: (slice, €), slices > 0 only. Pure (R488).

    The net comes from its own view (`_load_net`), never `gross − deductions`; the
    transferred part is what the bank statement shows, the rest of the net waits for
    the next quarterly transfer."""
    paid = min(max(paid, 0.0), net) if net > 0 else 0.0
    parts = [(t("sacem.deductions", "🧾 Retenues"), abs(deductions)),
             (t("sacem.paid", "🏦 Déjà viré"), paid),
             (t("sacem.pending", "⏳ À virer"), net - paid)]
    return [(k, round(v, 2)) for k, v in parts if round(v, 2) > 0]


def royalties_pie(gross: float, parts: list[tuple[str, float]]):
    """The SACEM gross as ONE pie — too few figures for anything else (owner W11)."""
    import plotly.graph_objects as go

    fig = go.Figure(go.Pie(
        labels=[k for k, _ in parts], values=[v for _, v in parts], hole=0.45, sort=False,
        marker={'colors': ["#B0A8B9", "#8E44AD", "#C39BD3"][:len(parts)]},
        texttemplate="%{label}<br>%{value:,.2f} €", textposition="outside",
        hovertemplate="%{label}<br>%{value:,.2f} € · %{percent}<extra></extra>"))
    fig.update_layout(
        title=t("sacem.pie_title", "SACEM : {g} de royalties brutes").format(
            g=f"{gross:,.2f} €".replace(",", " ")),
        height=380, showlegend=False, margin={'t': 60, 'b': 30})
    return fig


def render_section(db, artist_id) -> None:
    """The SACEM block, on the page and connection of its caller (rule 9: one per view)."""
    st.subheader(t("sacem.title", "🎼 Royalties SACEM"))
    with st.expander(t("sacem.howto_header", "📥 Comment obtenir votre relevé SACEM")):
        st.markdown(t("sacem.howto_body",
                      "1. Connectez-vous sur **sacem.fr** (espace membre).\n"
                      "2. **Mes répartitions** → **Relevé de compte**.\n"
                      "3. Réglez le filtre de **date sur « depuis l'inscription »** (pour tout "
                      "l'historique).\n"
                      "4. **Téléchargez le fichier `.xlsx`**.\n"
                      "5. Importez-le dans l'onglet **📂 Ajouter mes chiffres** des Credentials "
                      "(le type SACEM est détecté automatiquement)."))

    # R389 (V80) : the statement is an .xlsx, not a CSV — said on the button, and the
    # button lands on the IMPORT tab, not the Credentials page's first tab.
    if st.button(t("sacem.import_btn", "📂 Importer mon relevé SACEM (.xlsx)"),
                 key="sacem_import"):
        from src.dashboard.views.credentials.router import CSV_TAB_KEY, goto_tab
        goto_tab(CSV_TAB_KEY)

    totals = _load_totals(db, artist_id)
    if not totals:
        st.info(t("sacem.no_data",
                  "Aucune donnée SACEM. Importe ton relevé de compte (.xlsx) avec le "
                  "bouton ci-dessus."))
        return

    gross = totals.get('repartition', 0.0)
    deductions, net = _load_net(db, artist_id)
    # R488 (W11 « SACEM : graphique circulaire, trop peu de données ») : the waterfall,
    # its two captions, the treasury note and the ledger table became ONE pie — the
    # gross split into deductions, transferred and still to transfer.
    from src.dashboard.utils import charts
    parts = royalties_split(gross, deductions, net, -totals.get('payout', 0.0))
    charts.plotly_chart(royalties_pie(gross, parts), width="stretch", decision=False)
