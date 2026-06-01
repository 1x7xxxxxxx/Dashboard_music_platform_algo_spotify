"""trigger_algo — router: the slim show() entry point (move-only split)."""
from datetime import date
from datetime import timedelta
from src.dashboard.utils import view_session
import streamlit as st
from ._common import (
    _load_lifecycle_benchmark,
    _load_ml_pred,
)
from ._tab_algos import _show_tab_algos
from ._tab_budget_roi import _show_tab_budget_roi
from ._tab_explainability import _show_tab_explainability
from ._tab_global import _show_tab_global
from ._tab_lifecycle import _show_tab_lifecycle
from ._tab_model import _show_tab_model


def show():
    from src.dashboard.auth import require_plan
    if not require_plan('basic'):
        return

    st.title("🚀 Road to Algorithms (J+28)")
    st.markdown("Suivi ML, budget, ROI et explainabilité des scores algorithmiques.")

    with view_session() as (db, artist_id):
        # Track list — ordered by release_date DESC from tracks table.
        # S4A CSVs replace '?' with '_' in song names, so the JOIN uses REPLACE().
        try:
            if artist_id:
                tracks = db.fetch_df(
                    """SELECT t.song
                       FROM (SELECT song FROM s4a_song_timeline
                             WHERE song NOT ILIKE %s AND artist_id = %s GROUP BY song) t
                       LEFT JOIN tracks tk ON REPLACE(tk.track_name, '?', '_') = t.song
                                              AND tk.saas_artist_id = %s
                       ORDER BY tk.release_date DESC NULLS LAST, t.song""",
                    ("%1x7xxxxxxx%", artist_id, artist_id)
                )["song"].tolist()
            else:
                tracks = db.fetch_df(
                    """SELECT t.song
                       FROM (SELECT song FROM s4a_song_timeline
                             WHERE song NOT ILIKE %s GROUP BY song) t
                       LEFT JOIN tracks tk ON REPLACE(tk.track_name, '?', '_') = t.song
                       ORDER BY tk.release_date DESC NULLS LAST, t.song""",
                    ("%1x7xxxxxxx%",)
                )["song"].tolist()
        except Exception:
            tracks = []

        if not tracks:
            st.warning("Aucune donnée de timeline disponible.")
            return

        # Global selectors
        today = date.today()
        sel1, sel2 = st.columns([2, 2])
        with sel1:
            selected_track = st.selectbox("🎵 Titre", tracks)

        # Fetch release_date of selected track via tracks table (same '?' → '_' normalisation).
        # tracks is tenant-scoped by saas_artist_id (migration 039); admin (None) = no filter.
        _track_frag = "AND saas_artist_id = %s" if artist_id else ""
        _track_params = (artist_id,) if artist_id else ()
        try:
            rd_rows = db.fetch_query(
                f"SELECT release_date FROM tracks WHERE REPLACE(track_name, '?', '_') = %s {_track_frag} LIMIT 1",
                (selected_track, *_track_params)
            )
            track_release_date = rd_rows[0][0] if rd_rows and rd_rows[0][0] else (today - timedelta(days=28))
        except Exception:
            track_release_date = today - timedelta(days=28)

        with sel2:
            _PRESETS = [
                "28 derniers jours",
                "90 derniers jours",
                "Mois en cours",
                "Mois précédent",
                "Mois / Année",
                "Personnalisé",
            ]
            period_preset = st.selectbox(
                "📅 Période",
                _PRESETS,
                key=f"period_preset_{selected_track}"
            )

        # Sub-selectors rendered below the two-column row (full width)
        import calendar as _cal
        _MONTHS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                   "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]

        if period_preset == "28 derniers jours":
            date_from, date_to = today - timedelta(days=28), today

        elif period_preset == "90 derniers jours":
            date_from, date_to = today - timedelta(days=90), today

        elif period_preset == "Mois en cours":
            date_from = today.replace(day=1)
            date_to = today

        elif period_preset == "Mois précédent":
            first_current = today.replace(day=1)
            date_to = first_current - timedelta(days=1)
            date_from = date_to.replace(day=1)

        elif period_preset == "Mois / Année":
            cm, cy = st.columns([1, 1])
            sel_month = cm.selectbox(
                "Mois", _MONTHS,
                index=today.month - 1,
                key=f"sel_month_{selected_track}"
            )
            sel_year = cy.selectbox(
                "Année",
                list(range(2022, today.year + 1))[::-1],
                key=f"sel_year_{selected_track}"
            )
            month_num = _MONTHS.index(sel_month) + 1
            date_from = date(sel_year, month_num, 1)
            last_day = _cal.monthrange(sel_year, month_num)[1]
            date_to = min(date(sel_year, month_num, last_day), today)

        else:  # Personnalisé
            _custom = st.date_input(
                "Plage personnalisée",
                value=(today - timedelta(days=28), today),
                max_value=today,
                key=f"period_custom_{selected_track}"
            )
            if isinstance(_custom, (list, tuple)) and len(_custom) == 2:
                date_from, date_to = _custom[0], _custom[1]
            else:
                date_from, date_to = today - timedelta(days=28), today

        # Load ML prediction + global benchmark once — shared across tabs
        ml_pred = _load_ml_pred(db, selected_track, artist_id)
        benchmark_df = _load_lifecycle_benchmark(db)

        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "🎯 Vue Globale",
            "📊 Suivi Algorithmes",
            "💰 Budget & ROI",
            "🔍 Explainabilité",
            "📈 Modèle",
            "📉 Cycle de vie & Benchmark",
        ])
        with tab1:
            _show_tab_global(db, selected_track, artist_id, date_from, date_to, ml_pred, release_date=track_release_date)
        with tab2:
            _show_tab_algos(db, selected_track, artist_id, date_from, date_to, ml_pred, release_date=track_release_date)
        with tab3:
            _show_tab_budget_roi(db, selected_track, artist_id, date_from, date_to)
        with tab4:
            _show_tab_explainability(db, ml_pred, selected_track, artist_id)
        with tab5:
            _show_tab_model(db, selected_track, artist_id)
        with tab6:
            _show_tab_lifecycle(db, selected_track, artist_id,
                                release_date=track_release_date, benchmark_df=benchmark_df)
