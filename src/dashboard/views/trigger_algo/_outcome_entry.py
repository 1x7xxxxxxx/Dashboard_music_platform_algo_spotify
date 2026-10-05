"""Road to Algo — enter the realised algo streams, where they are judged.

Type: Sub
Uses: streamlit, pandas, src.dashboard.utils.entry_period, src.dashboard.utils.ui.flash, i18n
Triggers: views/trigger_algo/router.py (« 📈 Ce qui s'est vraiment passé »)
Persists in: s4a_song_algo_outcomes

R376 (2026-10-05, owner's screen review): the S4A entry page carried three tabs —
signals, realised results, « ce que ça donne ». The realised results are not a monthly
signal: they are the LABEL of a prediction, typed ~4 weeks after it, and the only place
they mean something is beside the prediction they judge. So the two grids moved here,
under the facts tab of the algo view, next to « Le pari du modèle ». Moved verbatim from
`views/saisie_s4a.py` (same widget keys, same i18n keys, same table).
"""
from datetime import date

import pandas as pd
import streamlit as st

from src.dashboard.utils.entry_period import entry_period_selector
from src.dashboard.utils.i18n import t
from src.dashboard.utils.ui import flash


def latest_algo_outcomes(db, artist_id, time_window) -> dict:
    """{song: {dw, rr, radio}} latest realized algo-stream snapshot per song for one window."""
    rows = db.fetch_query(
        """SELECT DISTINCT ON (song) song, dw_streams, rr_streams, radio_streams
           FROM s4a_song_algo_outcomes
           WHERE artist_id = %s AND time_window = %s
           ORDER BY song, recorded_at DESC""",
        (artist_id, time_window)) if artist_id else []
    return {r[0]: {"dw": int(r[1] or 0), "rr": int(r[2] or 0), "radio": int(r[3] or 0)}
            for r in rows} if rows else {}


def render_outcome_grid(db, artist_id, tracks) -> None:
    st.subheader(t("saisie_s4a.outcome_header",
                   "🎯 Streams algorithmiques réalisés (28j) — entraînement du modèle"))
    st.caption(t("saisie_s4a.outcome_caption",
                 "Par titre, les streams **réellement obtenus** sur 28 jours via Discover Weekly, "
                 "Release Radar et Radio. Ces valeurs deviennent les **labels** qui apprennent au "
                 "modèle s'il avait raison (boucle d'apprentissage live, alimente ml_prediction_outcomes)."))

    with st.expander(t("saisie_s4a.outcome_howto_header",
                       "ℹ️ Où lire les streams DW / RR / Radio dans Spotify for Artists ?")):
        st.markdown(t("saisie_s4a.outcome_howto",
            "**Musique → Titres → un titre → Source de streams**, active le filtre **28 derniers "
            "jours**, puis reporte les lignes **Discover Weekly**, **Release Radar** et **Radio** de la "
            "segmentation « Source de streams ». Saisis ces valeurs **~4 semaines après** la prédiction "
            "pour que la fenêtre de 28 jours soit complète — c'est ce délai qui rend le label honnête."))

    out7 = latest_algo_outcomes(db, artist_id, "7d")
    out28 = latest_algo_outcomes(db, artist_id, "28d")
    df = pd.DataFrame([{
        "Titre": s,
        "DW 7j": out7.get(s, {}).get("dw", 0), "DW 28j": out28.get(s, {}).get("dw", 0),
        "RR 7j": out7.get(s, {}).get("rr", 0), "RR 28j": out28.get(s, {}).get("rr", 0),
        "Radio 7j": out7.get(s, {}).get("radio", 0), "Radio 28j": out28.get(s, {}).get("radio", 0),
    } for s in tracks])

    _num = st.column_config.NumberColumn(min_value=0, step=1)
    edited = st.data_editor(
        df, hide_index=True, width="stretch", num_rows="fixed",
        column_config={
            "Titre": st.column_config.TextColumn(disabled=True),
            "DW 7j": _num,
            "DW 28j": st.column_config.NumberColumn(
                min_value=0, step=1,
                help=t("saisie_s4a.outcome_help",
                       "Streams Discover Weekly / Release Radar / Radio réels. Le 28j alimente les "
                       "labels d'entraînement du modèle (seuils 137 / 130 / 639) ; le 7j sert au suivi.")),
            "RR 7j": _num, "RR 28j": _num, "Radio 7j": _num, "Radio 28j": _num,
        },
        key=f"grid_outcome_{artist_id}",
    )

    if st.button(t("saisie_s4a.save_outcomes", "💾 Enregistrer les outcomes (7j + 28j)"),
                 type="primary", key=f"save_outcomes_{artist_id}"):
        today = date.today()
        rows = []
        for _, r in edited.iterrows():
            rows.append({"artist_id": artist_id, "song": r["Titre"], "time_window": "7d",
                         "recorded_at": today, "dw_streams": int(r["DW 7j"] or 0),
                         "rr_streams": int(r["RR 7j"] or 0), "radio_streams": int(r["Radio 7j"] or 0)})
            rows.append({"artist_id": artist_id, "song": r["Titre"], "time_window": "28d",
                         "recorded_at": today, "dw_streams": int(r["DW 28j"] or 0),
                         "rr_streams": int(r["RR 28j"] or 0), "radio_streams": int(r["Radio 28j"] or 0)})
        try:
            db.upsert_many("s4a_song_algo_outcomes", rows,
                           ["artist_id", "song", "time_window", "recorded_at"],
                           ["dw_streams", "rr_streams", "radio_streams"])
            flash(t("saisie_s4a.saved_outcomes",
                         "Outcomes réalisés enregistrés (7j + 28j) pour {n} titres.").format(n=len(tracks)))
            st.rerun()
        except Exception as exc:
            st.error(t("saisie_s4a.error", "Erreur : {exc}").format(exc=exc))


def render_outcome_custom_grid(db, artist_id, tracks) -> None:
    st.markdown("**" + t("saisie_s4a.outcome_custom_header",
                         "📅 Autre fenêtre (streams DW/RR/Radio générés)") + "**")
    # ⚠️ DES RACCOURCIS, PAS DEUX DATES À TAPER — 2026-09-22.
    # « début fin avec des valeurs à rentrer c'est pas très agréable ». Et le fond
    # dépasse le confort : les seules fenêtres pour lesquelles S4A affiche un chiffre
    # sont 7 j, 28 j et 12 mois. Une paire de dates libres invite à saisir une période
    # dont la source ne produit aucune valeur. Détail : `utils/entry_period.py`.
    fenetre = entry_period_selector(key=f"algo_custom_{artist_id}")
    start, end = fenetre.start, fenetre.end

    df = pd.DataFrame([{"Titre": s, "DW": 0, "RR": 0, "Radio": 0} for s in tracks])
    _num = st.column_config.NumberColumn(min_value=0, step=1)
    edited = st.data_editor(
        df, hide_index=True, width="stretch", num_rows="fixed",
        column_config={"Titre": st.column_config.TextColumn(disabled=True),
                       "DW": _num, "RR": _num, "Radio": _num},
        key=f"grid_outcome_custom_{artist_id}",
    )
    if st.button(t("saisie_s4a.outcome_custom_save", "💾 Enregistrer la période (algos)"),
                 type="primary", key=f"save_outcome_custom_{artist_id}"):
        rows = [{"artist_id": artist_id, "song": r["Titre"], "time_window": "custom",
                 "recorded_at": end, "dw_streams": int(r["DW"] or 0), "rr_streams": int(r["RR"] or 0),
                 "radio_streams": int(r["Radio"] or 0), "period_start": start, "period_end": end}
                for _, r in edited.iterrows()]
        try:
            db.upsert_many("s4a_song_algo_outcomes", rows,
                           ["artist_id", "song", "time_window", "recorded_at"],
                           ["dw_streams", "rr_streams", "radio_streams", "period_start", "period_end"])
            flash(t("saisie_s4a.outcome_custom_saved",
                         "Période {start} → {end} enregistrée pour {n} titres.")
                       .format(start=start, end=end, n=len(rows)))
            st.rerun()
        except Exception as exc:
            st.error(t("saisie_s4a.error", "Erreur : {exc}").format(exc=exc))
