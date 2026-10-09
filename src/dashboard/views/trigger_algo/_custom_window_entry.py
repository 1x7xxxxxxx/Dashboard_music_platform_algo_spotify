"""Road to Algo — enter playlist adds over another window (first days after a release).

Type: Sub
Uses: streamlit, pandas, src.dashboard.utils.entry_period, s4a_entry_insight, ui.flash, i18n
Triggers: views/trigger_algo/router.py (« Ce qui s'est vraiment passé »), after the outcomes
Persists in: s4a_song_playlist_adds (time_window = 'custom')

R481 (W4, owner 2026-10-09) : « le tableau autre fenêtre / streams → Prédiction
déclenchement algo ». It left « 📝 Saisie S4A », which keeps only the monthly signals and
the titles they cover.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard.utils.date_format import format_date
from src.dashboard.utils.entry_period import POST_RELEASE, entry_period_selector
from src.dashboard.utils.i18n import t
from src.dashboard.utils.s4a_entry_insight import load_entry_tracks, load_release_dates
from src.dashboard.utils.ui import flash


def render_custom_grid(db, artist_id) -> None:
    """« Autre fenêtre » : playlist adds over a window counted from one release."""
    tracks = load_entry_tracks(db, artist_id)
    if not tracks:
        return
    st.subheader(t("saisie_s4a.custom_header",
                   "📅 Autre fenêtre (ex. premiers jours post-release)"))
    # Même raison qu'au-dessus. J+1 … J+7 et « Depuis la sortie » sont ici les
    # raccourcis utiles : c'est exactement le cas que ce bloc existe pour servir. Ils
    # se comptent depuis la sortie D'UN titre — on le choisit, le plus récent d'abord
    # (R441, 2026-10-07). Avant, `release` n'était jamais passé : « Depuis la sortie »
    # retombait toujours sur 28 jours.
    releases = load_release_dates(db, artist_id)
    ref = st.selectbox(
        t("saisie_s4a.custom_release", "Sortie de référence"), tracks,
        format_func=lambda s: (f"{s} — {format_date(releases[s])}" if s in releases
                               else s),
        key=f"custom_ref_{artist_id}")
    fenetre = entry_period_selector(key=f"custom_{artist_id}", release=releases.get(ref),
                                    post_release=True)
    start, end = fenetre.start, fenetre.end
    # Une fenêtre comptée depuis UNE sortie ne vaut que pour ce titre-là.
    anchored = fenetre.preset == "release" or fenetre.preset in POST_RELEASE
    rows_for = [ref] if anchored else tracks

    df = pd.DataFrame([{"Titre": s, "Ajouts playlist": 0} for s in rows_for])
    edited = st.data_editor(
        df, hide_index=True, width="stretch", num_rows="fixed",
        column_config={
            "Titre": st.column_config.TextColumn(disabled=True),
            "Ajouts playlist": st.column_config.NumberColumn(min_value=0, step=1),
        },
        key=f"grid_custom_{artist_id}",
    )
    if st.button(t("saisie_s4a.save_custom", "💾 Enregistrer la plage personnalisée"), type="primary"):
        rows = [{"artist_id": artist_id, "song": r["Titre"], "time_window": "custom",
                 "recorded_at": end, "count": int(r["Ajouts playlist"] or 0),
                 "period_start": start, "period_end": end} for _, r in edited.iterrows()]
        try:
            db.upsert_many("s4a_song_playlist_adds", rows,
                           ["artist_id", "song", "time_window", "recorded_at"],
                           ["count", "period_start", "period_end"])
            flash(t("saisie_s4a.saved_custom", "Plage {start} → {end} enregistrée pour {n} titres.")
                       .format(start=start, end=end, n=len(rows)))
            st.rerun()
        except Exception as exc:
            st.error(t("saisie_s4a.error", "Erreur : {exc}").format(exc=exc))
