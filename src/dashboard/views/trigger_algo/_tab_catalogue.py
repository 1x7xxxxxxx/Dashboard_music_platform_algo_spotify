"""🎯 Où en sont mes titres — l'écran du premier coup d'œil.

Type: Sub
Uses: streamlit, pandas, plotly, ._catalogue, src.dashboard.utils.semantic_colors
Depends on: ml_song_predictions (lu ICI, dans la fonction qui dessine)
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

def _show_tab_catalogue(db, artist_id) -> None:
    """Les dix titres, classés par ce qui leur manque le moins."""
    if not artist_id:
        st.info(t("trigger_algo.cat.admin",
                  "Sélectionne un artiste pour voir son catalogue."))
        return
    try:
        lignes = db.fetch_df(_Q_CATALOGUE, (artist_id, artist_id))
    except Exception:                                    # noqa: BLE001
        st.info(t("trigger_algo.cat.unreadable",
                  "Catalogue illisible pour le moment — ce n'est pas « aucun titre »."))
        return

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
        return

    df = construire(lignes.to_dict("records"))

    # R477 (owner W14, 2026-10-09) : « dernière release sélectionnée automatiquement »,
    # « deux releases au lieu de cinq, pas de tableau, des graphiques ». The three tiles,
    # the head texts, the note under the gauges and « 📋 Le tableau complet » (with its
    # note — « le vrai pour tout ton catalogue ») are gone: the two figures ARE the answer.
    # The selector is the app's shared one (`release_picker`, R478), newest release first.
    from src.dashboard.utils.release_picker import release_picker
    from ._release_targets import (MAX_TRACKS, by_proximity, indicators_figure,
                                   last_releases, track_levers, values_figure)
    newest_first = last_releases(df, n=len(df))
    choix = release_picker(t("trigger_algo.cat.releases", "🎵 Tes deux dernières sorties"),
                           newest_first, key=f"cat_compare_{artist_id}")
    # The cap is applied HERE, not by `max_selections`: Streamlit RAISES when the session
    # already holds more (this key served the uncapped selector before R247), and a
    # widened filter crashed the tab (test_a_widened_filter_still_renders).
    if len(choix) > MAX_TRACKS:
        st.caption(t("trigger_algo.cat.releases_cut",
                     "Les {n} premiers titres choisis sont montrés.").format(n=MAX_TRACKS))
        choix = choix[:MAX_TRACKS]
    if not choix:
        return
    feats_of = {r["song"]: _feats_json(r.get("features_json")) for r in lignes.to_dict("records")}
    levers = {s_: track_levers(feats_of.get(s_, {})) for s_ in choix}
    charts.plotly_chart(indicators_figure(by_proximity(choix, levers), levers),
                        width="stretch")
    charts.plotly_chart(values_figure(choix, levers), width="stretch")
