"""SACEM royalties — a SECTION of the distributors page since R461.

Type: Sub
Uses: i18n, credentials.router.goto_tab
Triggers: called by views.imusician.show() (R461 — owner, 2026-10-07: « fusionne les
          deux en un … Distributeur iMusician DistroKid + SACEM »). `?page=sacem` is an
          alias of `imusician` (routes.PAGE_ALIASES).
Persists in: — (reads sacem_statement, written by the SACEM xlsx import)

Free-tier. Shows the SACEM account statement: gross royalties (REPARTITION lines),
social charges (CSG/CRDS/URSSAF), the net actually paid and the bank transfers to
date — one pie from R488 to R519; since R519 the SACEM money is a series of the page's
one money-flow figure, and this section keeps the how-to and the import button. The
gross royalties also feed the break-even of the cross view's « Revenus » section.

No total is computed here: the presence check reads `v_sacem_monthly` (migration 111),
and the figure reads the net through `v_artist_monthly_cashflow` (migration 133). The netting rule — which
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
    # R519 (owner X11 II): the donut left — the SACEM net is a series of the page's
    # one money-flow figure (`treasury_chart.cashflow_figure`), above this section.
