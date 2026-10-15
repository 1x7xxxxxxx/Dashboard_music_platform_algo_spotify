"""Saisie streams algorithmiques — what happened once a playlist opened (R587).

Type: Feature
Uses: views.trigger_algo._outcome_entry, views.trigger_algo._custom_window_entry,
      views.revenue_forecast (titles, cost label)
Depends on: s4a_song_algo_outcomes, s4a_song_playlist_adds, artist_cost_entries
Persists in: s4a_song_algo_outcomes, s4a_song_playlist_adds, artist_cost_entries

R587 (owner, Prédiction algos 2026-10-15): the « une fois déclenché » grids — realised
algo streams, playlist adds J+1, J+2… — left the prediction page, which is read, for the
« Configuration et saisie manuelle » section, after « 💰 Saisie trésorerie ». The
distribution cost of a release is entered here too: it is typed per title, the day the
title goes out — the same gesture as its streams. Free, like every entry that feeds the
model (R405).
"""
from datetime import date

import streamlit as st

from src.dashboard.utils import view_session
from src.dashboard.utils.i18n import t
from src.dashboard.utils.ui import flash


def show() -> None:
    from src.dashboard.views.trigger_algo._custom_window_entry import render_custom_grid
    from src.dashboard.views.trigger_algo._outcome_entry import render_outcomes

    st.title(t("saisie_algo.title", "🎯 Saisie streams algorithmiques"))
    with view_session() as (db, artist_id):
        render_outcomes(db, artist_id)
        st.markdown("---")
        render_custom_grid(db, artist_id)
        st.markdown("---")
        render_distribution_cost(db, artist_id)


def render_distribution_cost(db, artist_id: int) -> None:
    """One release's distribution cost — a one-off cost on its title (R587)."""
    from src.dashboard.views.revenue_forecast import _artist_tracks, cost_label

    st.subheader(t("saisie_algo.cost_header", "💳 Coût de distribution d'une sortie"))
    with st.form("release_distribution_cost", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 1, 1])
        titre = c1.selectbox(t("saisie_algo.cost_track", "Titre"),
                             _artist_tracks(db, artist_id) or ["—"])
        montant = c2.number_input(t("saisie_algo.cost_amount", "Montant (€)"),
                                  min_value=0.0, step=1.0, value=0.0)
        mois = c3.date_input(t("saisie_algo.cost_month", "Mois"),
                             value=date.today().replace(day=1))
        if st.form_submit_button(t("saisie_algo.cost_save", "💾 Enregistrer"),
                                 type="primary"):
            if montant <= 0 or titre == "—":
                st.warning(t("saisie_algo.cost_zero",
                             "Choisis un titre et un montant supérieur à zéro."))
                return
            save_distribution_cost(db, artist_id, titre, float(montant), mois,
                                   cost_label("", titre, "distribution"))
            flash(t("saisie_algo.cost_saved",
                    "✅ {m:.2f} € de distribution enregistrés pour « {s} »."
                    ).format(m=float(montant), s=titre))
            st.rerun()


def save_distribution_cost(db, artist_id: int, song: str, amount: float, month: date,
                           label: str | None) -> None:
    """One one-off `distribution` row, on the tenant, in the month it was paid."""
    db.execute_query(
        """INSERT INTO artist_cost_entries
           (artist_id, category, label, amount_eur, billing_period, start_month, end_month)
           VALUES (%s, 'distribution', %s, %s, 'one_off', %s, NULL)""",
        (artist_id, label or song, amount, month.replace(day=1)))
