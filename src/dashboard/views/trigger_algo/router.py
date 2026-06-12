"""trigger_algo — router: the slim show() entry point (move-only split)."""
from datetime import date
from datetime import timedelta
from src.dashboard.utils import view_session
from src.dashboard.utils.i18n import t
from src.utils.track_matching import canonical_song_sql
import streamlit as st
from ._common import (
    _load_lifecycle_benchmark,
    _load_ml_pred,
)
from ._tab_algo_streams import _show_tab_algo_streams
from ._tab_algos import _show_tab_algos
from ._tab_budget_roi import _show_tab_budget_roi
from ._tab_explainability import _show_tab_explainability
from ._tab_global import _show_tab_global
from ._tab_lifecycle import _show_tab_lifecycle
from ._tab_model import _show_tab_model


def show():
    from src.dashboard.auth import require_plan
    if not require_plan('premium'):
        return

    st.title(t("trigger_algo.title", "🚀 Road to Algorithms (J+28)"))
    st.markdown(t("trigger_algo.subtitle",
                  "Suivi ML, budget, ROI et explainabilité des scores algorithmiques."))

    with st.expander(t("trigger_algo.guide_expander",
                       "📖 Comment lire cette page (guide artiste) — à ouvrir une fois"),
                     expanded=False):
        st.markdown(t(
            "trigger_algo.guide_body",
            "Cette page répond à **une seule question** : *« Spotify va-t-il pousser mon "
            "titre tout seul dans ses algorithmes ? »* Les **28 premiers jours** après la "
            "sortie (J+28) sont décisifs — c'est la fenêtre où les algorithmes décident.\n\n"

            "**🎚️ Les 3 algorithmes suivis**\n"
            "- 💎 **Discover Weekly (DW)** — playlist perso hebdomadaire envoyée à des auditeurs "
            "qui ne te connaissent PAS encore. C'est la découverte pure, le Graal pour gagner de "
            "nouveaux fans. La porte la plus dure à ouvrir.\n"
            "- 📡 **Release Radar (RR)** — playlist hebdo poussée à **tes abonnés** à chaque "
            "sortie. Plus facile à déclencher (ils te suivent déjà), mais touche surtout ton "
            "audience existante.\n"
            "- 📻 **Radio** — flux algorithmique « infini » qui enchaîne des titres similaires. "
            "Signe que Spotify te juge « fiable » pour nourrir ses recommandations. Demande le "
            "plus de volume de streams.\n\n"

            "**🔢 Les 2 chiffres à NE PAS confondre**\n"
            "- **DW % / RR % / Radio %** = probabilité **absolue et calibrée** de déclenchement "
            "(50 % = vraiment 1 chance sur 2). C'est LA mesure de ta vraie chance. Bandes de "
            "décision : 🔴 < 20 % **STOP** · 🟠 20–50 % **OPTIMISER** · 🟢 ≥ 50 % **SCALER**.\n"
            "- **Score /20** = **classement interne** de ton catalogue (meilleur titre = 20, "
            "pire = 0). Sert à savoir *quel titre pousser en priorité*, PAS à lire une chance de "
            "trigger. Un titre peut être 20/20 avec seulement 10 % de proba réelle.\n\n"

            "**🧭 Les notions clés**\n"
            "- **Popularity Index (0–100)** — la « note de popularité » Spotify du titre. C'est "
            "la porte d'entrée : chaque algo a un PI minimum. Plus ton PI monte, plus les portes "
            "s'ouvrent.\n"
            "- **Seuils elbow (28j)** — volume d'algo-streams **générés par la playlist "
            "elle-même** qui marque le *début* d'un trigger : **~130 (RR)**, **~137 (DW)**, "
            "**~639 (Radio)**. C'est le minimum que la playlist produit une fois déclenchée — "
            "**pas** le nombre de streams à générer soi-même pour la déclencher.\n"
            "- **Velocity (momentum)** — vitesse d'accélération récente des streams. Un titre qui "
            "monte vite est favorisé ; un titre à plat stagne.\n"
            "- **Discovery Mode** — option Spotify (commission sur tes royalties) qui force "
            "l'entrée en Radio. À activer/désactiver selon le contexte (onglet Suivi "
            "Algorithmes).\n\n"

            "**🗂️ Les onglets**\n"
            "- 🎯 **Vue Globale** — métriques du titre + probas + son classement /20.\n"
            "- 📊 **Suivi Algorithmes** — verdict, leviers d'action, trajectoire J+28, portes par PI.\n"
            "- 💰 **Budget & ROI** — combien dépenser en pub et quand.\n"
            "- 🔍 **Explainabilité** — *pourquoi* le modèle donne ce score (SHAP, leviers).\n"
            "- 📈 **Modèle** — fiabilité technique du modèle ML.\n"
            "- 📉 **Cycle de vie & Benchmark** — où en est ton titre vs les autres, dans le temps.\n\n"

            "⚠️ **Limite honnête** : le modèle prédit BIEN *si* un titre va déclencher "
            "(classification, AUC ~0.92), mais MAL *combien* de streams il fera (le volume n'est "
            "pas fiable). **Fie-toi aux %, pas aux prévisions de volume en €.**"
        ))

    with view_session() as (db, artist_id):
        # Track list — ordered by release_date DESC from tracks table.
        # S4A CSVs replace '?' with '_' in song names, so the JOIN uses REPLACE().
        try:
            if artist_id:
                tracks = db.fetch_df(
                    f"""SELECT t.song
                       FROM (SELECT song FROM s4a_song_timeline
                             WHERE song NOT ILIKE %s AND artist_id = %s GROUP BY song) t
                       LEFT JOIN tracks tk ON {canonical_song_sql('tk.track_name')} = t.song
                                              AND tk.saas_artist_id = %s
                       ORDER BY tk.release_date DESC NULLS LAST, t.song""",
                    ("%1x7xxxxxxx%", artist_id, artist_id)
                )["song"].tolist()
            else:
                tracks = db.fetch_df(
                    f"""SELECT t.song
                       FROM (SELECT song FROM s4a_song_timeline
                             WHERE song NOT ILIKE %s GROUP BY song) t
                       LEFT JOIN tracks tk ON {canonical_song_sql('tk.track_name')} = t.song
                       ORDER BY tk.release_date DESC NULLS LAST, t.song""",
                    ("%1x7xxxxxxx%",)
                )["song"].tolist()
        except Exception:
            tracks = []

        if not tracks:
            st.warning(t("trigger_algo.no_timeline", "Aucune donnée de timeline disponible."))
            return

        # Global selectors
        today = date.today()
        sel1, sel2 = st.columns([2, 2])
        with sel1:
            selected_track = st.selectbox(t("trigger_algo.sel_track", "🎵 Titre"), tracks)

        # Fetch release_date of selected track via tracks table (same '?' → '_' normalisation).
        # tracks is tenant-scoped by saas_artist_id (migration 039); admin (None) = no filter.
        _track_frag = "AND saas_artist_id = %s" if artist_id else ""
        _track_params = (artist_id,) if artist_id else ()
        try:
            rd_rows = db.fetch_query(
                f"SELECT release_date FROM tracks WHERE {canonical_song_sql('track_name')} = %s {_track_frag} LIMIT 1",
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
                t("trigger_algo.sel_period", "📅 Période"),
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
                t("trigger_algo.sel_month", "Mois"), _MONTHS,
                index=today.month - 1,
                key=f"sel_month_{selected_track}"
            )
            sel_year = cy.selectbox(
                t("trigger_algo.sel_year", "Année"),
                list(range(2022, today.year + 1))[::-1],
                key=f"sel_year_{selected_track}"
            )
            month_num = _MONTHS.index(sel_month) + 1
            date_from = date(sel_year, month_num, 1)
            last_day = _cal.monthrange(sel_year, month_num)[1]
            date_to = min(date(sel_year, month_num, last_day), today)

        else:  # Personnalisé
            _custom = st.date_input(
                t("trigger_algo.sel_custom_range", "Plage personnalisée"),
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

        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            t("trigger_algo.tab_global", "🎯 Vue Globale"),
            t("trigger_algo.tab_algos", "📊 Suivi Algorithmes"),
            t("trigger_algo.tab_budget", "💰 Budget & ROI"),
            t("trigger_algo.tab_explain", "🔍 Explainabilité"),
            t("trigger_algo.tab_model", "📈 Modèle"),
            t("trigger_algo.tab_lifecycle", "📉 Cycle de vie & Benchmark"),
            t("trigger_algo.tab_algostreams", "📈 Streams algos générés"),
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
        with tab7:
            _show_tab_algo_streams(db, selected_track, artist_id)
