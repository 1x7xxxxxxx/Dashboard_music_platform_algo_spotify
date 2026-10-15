"""Saisie trésorerie — every euro typed by hand, on its own page (R585).

Type: Feature
Uses: views.imusician (revenue entry + deletion), views.revenue_forecast (cost entry)
Depends on: imusician_monthly_revenue, distrokid_monthly_revenue, artist_cost_entries
Persists in: imusician_monthly_revenue, distrokid_monthly_revenue, artist_cost_entries

R585 (owner, Trésorerie 2026-10-15): the manual entry left the Trésorerie page, which is
read, for the « Configuration et saisie manuelle » section, after Hypeddit — the other
hand-typed source. Trésorerie keeps two buttons: the export import and this page.
"""
import streamlit as st

from src.dashboard.utils import get_db_connection, require_db
from src.dashboard.utils.i18n import t


def show() -> None:
    from src.dashboard.views import imusician
    from src.dashboard.views.revenue_forecast import _render_cost_entry

    st.title(t("saisie_tresorerie.title", "💰 Saisie trésorerie"))
    db = require_db(get_db_connection())
    try:
        artist_id, _ = imusician._get_artist_filter()
        imusician._render_entry_form(db, artist_id)
        imusician._render_delete(db, artist_id)
        st.markdown("---")
        target = imusician._money_target(db, artist_id)
        if target is not None:
            _render_cost_entry(db, target)
    finally:
        db.close()
