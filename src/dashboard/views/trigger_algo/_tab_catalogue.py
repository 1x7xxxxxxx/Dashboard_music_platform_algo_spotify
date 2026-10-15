"""🎯 Où en sont mes titres — l'écran du premier coup d'œil.

Type: Sub
Uses: streamlit, pandas, plotly, ._catalogue, src.dashboard.utils.semantic_colors
Depends on: ml_song_predictions (lu ICI, dans la fonction qui dessine), v_meta_campaign_daily
            (meilleur CPR, R581), algo_stream_estimates.json + s4a_song_timeline (R583)
Triggers: views/trigger_algo/router.py
Persists in: nothing

Ce que cet onglet remplace, et pourquoi
----------------------------------------
« Vue Globale » ouvrait sur onze figures et un tableau classé par `Score /20`. Ce
score étirait en min-max sur une échelle de 20 un écart de probabilité de **0,36
point**, mesuré sur les dix titres de l'artiste 1 le 2026-09-22 : il fabriquait un
classement à partir d'une donnée qui n'en portait aucun.

Ici, quatre figures au premier écran — trois tuiles et un graphe — et un tableau.
Le classement est l'**avancement vers la porte la plus proche** : mesuré de 0,0075 à
0,9896 sur les mêmes dix titres, dans l'unité du geste, et il bouge quand l'artiste
agit. La logique vit dans `_catalogue.py`, qui est pur et testé.

⚠️ La figure est dessinée DANS la fonction qui lit la base, et non dans une fabrique
appelée d'ailleurs. Le traceur de `tools/dev/gold_coverage.py` attribue une figure
par les lectures de sa tranche ; une figure fabriquée ailleurs devient
« indéterminée », et ce compteur est à 7 pour un plafond de 7.
"""
from __future__ import annotations

import streamlit as st

from src.dashboard.utils.i18n import t


from ._catalogue import _feats as _feats_json, construire
from src.dashboard.utils import charts

# R477 : no probability column — the tab shows none since « 📋 Le tableau complet » left.
_Q_CATALOGUE = """
SELECT song, days_since_release, streams_28d, features_json
  FROM ml_song_predictions
 WHERE artist_id = %s
   AND prediction_date = (SELECT MAX(prediction_date)
                            FROM ml_song_predictions WHERE artist_id = %s)
"""

def _show_tab_catalogue(db, artist_id) -> list[str]:
    """The picked releases' gauges and levers; returns the picks — they drive the page (R570)."""
    if not artist_id:
        st.info(t("trigger_algo.cat.admin",
                  "Sélectionne un artiste pour voir son catalogue."))
        return []
    try:
        lignes = db.fetch_df(_Q_CATALOGUE, (artist_id, artist_id))
    except Exception:                                    # noqa: BLE001
        st.error(t("trigger_algo.cat.unreadable",
                  "Catalogue illisible pour le moment — ce n'est pas « aucun titre »."))
        return []

    if lignes is None or lignes.empty:
        # ⚠️ L'ÉTAT VIDE EST LA PREMIÈRE CHOSE QUE VOIT UN CLIENT PREMIUM.
        # Mesuré le 2026-09-22 : `ml_song_predictions` ne porte que le propriétaire
        # et le bac à sable. Aucun artiste bêta n'a de prédiction, et la cause est
        # en amont — sans dépôt de CSV Spotify for Artists, aucun titre n'a d'écoute
        # sur 35 jours, donc le scoring nocturne ne trouve rien à noter.
        st.info(t("trigger_algo.cat.empty",
                  "**Ton catalogue n'a pas encore été noté.** Le calcul tourne chaque "
                  "nuit dès qu'un titre a au moins une écoute sur les 35 derniers "
                  "jours. Il lui faut tes données Spotify for Artists : dépose-les "
                  "sur la page **📝 Saisie S4A**."))
        return []

    df = construire(lignes.to_dict("records"))

    # R579 (owner, 2026-10-15) — two separate filters: the reference release (newest by
    # default) and the one it is compared with (second-newest by default, or none).
    from ._release_targets import (by_proximity, comparison_options, indicators_figure,
                                   last_releases, lever_weights, track_levers,
                                   values_figure)
    newest_first = last_releases(df, n=len(df))
    if not newest_first:
        return []
    left, right = st.columns(2)
    ref = left.selectbox(t("trigger_algo.cat.reference", "🎵 Sortie de référence"),
                         newest_first, index=0, key=f"cat_ref_{artist_id}")
    options = comparison_options(newest_first, ref)
    cmp_ = right.selectbox(t("trigger_algo.cat.comparison", "🎵 Comparée à"), options,
                           index=1 if len(options) > 1 else 0, key=f"cat_cmp_{artist_id}",
                           format_func=lambda o: o or t("trigger_algo.cat.no_comparison",
                                                        "— aucune —"))
    choix = [ref] + ([cmp_] if cmp_ else [])
    feats_of = {r["song"]: _feats_json(r.get("features_json")) for r in lignes.to_dict("records")}
    levers = {s_: track_levers(feats_of.get(s_, {})) for s_ in choix}
    # R559 (fiches 46, 56, 57) — the 28-day figures and the SHAP weights
    # ride on the gauges: fiche 56's threshold bars said the same thing a second time.
    weights = lever_weights({s_: feats_of.get(s_, {}) for s_ in choix})
    # R571 — the windows end on the last IMPORTED S4A day; the gauge says which one.
    from src.utils.import_window import s4a_last_day_value
    until = s4a_last_day_value(db, artist_id)
    stats = {r["song"]: {"streams": r["streams_28d"], "saves": r["saves_28d"],
                         "adds": r["adds_28d"], "until": until}
             for r in df.to_dict("records") if r["song"] in choix}
    money, readings = _money_and_readings(db, artist_id, choix)
    charts.plotly_chart(indicators_figure(by_proximity(choix, levers), levers, weights, stats,
                                          feats={s_: feats_of.get(s_, {}) for s_ in choix},
                                          money=money, readings=readings),
                        width="stretch")
    st.divider()
    fig = values_figure(choix, levers, weights,
                        feats={s_: feats_of.get(s_, {}) for s_ in choix})
    if fig is not None:
        charts.plotly_chart(fig, width="stretch")
        # R582 — what the bars and their « repère » say, once, under the chart.
        st.caption(t("trigger_algo.cat.values_note",
                     "Chaque barre : où en est le titre sur un critère, en % de la valeur qui "
                     "déclenche la playlist selon le modèle (100 % = elle part, les autres "
                     "critères inchangés). Nombres : valeur actuelle / valeur visée. "
                     "« repère » : le modèle n'atteint jamais 80 % sur ce critère seul — la "
                     "cible vient alors de la base de connaissance. Barre pleine = sortie de "
                     "référence, hachurée = sortie comparée."))
    return list(choix)


def _money_and_readings(db, artist_id, choix: list[str]) -> tuple[dict, dict]:
    """R581/R583 — the best CPR, each title's € per stream, the cohort estimates and each
    title's measured algo streams. A part that cannot be read is left out, never invented."""
    from src.dashboard.utils.algo_preview_data import lire_cpr_bornes
    from src.dashboard.utils.artist_cashflow import track_stream_rate
    from ._tab_algo_streams import load_estimates, load_readings, release_date
    bornes = lire_cpr_bornes(db, artist_id)
    rates = {}
    for s_ in choix:
        r = track_stream_rate(db, artist_id, s_)
        rates[s_] = r["eur_par_stream"] if r else None
    money = {"cpr": bornes[0] if bornes else None, "rate": rates, "est": load_estimates()}
    readings = {s_: load_readings(db, artist_id, s_, release_date(db, artist_id, s_))
                for s_ in choix}
    return money, readings
