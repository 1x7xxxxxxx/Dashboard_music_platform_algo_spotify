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

import pandas as pd
import streamlit as st

from src.dashboard.utils.i18n import t
from src.dashboard.utils.semantic_colors import ATTENTION, BON, MAUVAIS, NEUTRE

from src.dashboard.utils.algo_preview_data import format_proba

from ._catalogue import _feats as _feats_json, construire, leviers_artiste
from src.dashboard.utils import charts

_Q_CATALOGUE = """
SELECT song, days_since_release, streams_28d,
       dw_probability, rr_probability, radio_probability, features_json
  FROM ml_song_predictions
 WHERE artist_id = %s
   AND prediction_date = (SELECT MAX(prediction_date)
                            FROM ml_song_predictions WHERE artist_id = %s)
"""

# Sous 40 % on est loin, au-dessus de 80 % la porte est à portée. Les bornes sont
# des repères de lecture, pas des seuils du modèle — elles n'entrent dans aucun calcul.
_PRESQUE, _EN_ROUTE = 0.80, 0.40


def _teinte(avancement) -> str:
    if avancement is None or pd.isna(avancement):
        return NEUTRE
    if avancement >= _PRESQUE:
        return BON
    return ATTENTION if avancement >= _EN_ROUTE else MAUVAIS


def _age(jours) -> str:
    if jours is None or pd.isna(jours):
        return "—"
    j = int(jours)
    if j < 60:
        return f"{j} j"
    if j < 365:
        return f"{j // 30} mois"
    annees, mois = divmod(j, 365)[0], (j % 365) // 30
    return f"{annees} an{'s' if annees > 1 else ''}" + (f" {mois} mois" if mois else "")


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

    # ── COMPARER DEUX OU TROIS TITRES CÔTE À CÔTE ───────────────────────────
    # Le tableau complet classe tout le catalogue ; il ne répond pas à « celui-ci
    # ou celui-là ? ». Le sélecteur FILTRE la figure et le tableau existants au
    # lieu d'ouvrir une seconde surface : deux vues du même chiffre finissent
    # toujours par diverger, et le cliquet de figures de premier écran ne laisse
    # pas la place à une figure de plus.
    # R247 (fiche 42) : tes DERNIÈRES SORTIES d'office, cinq au plus — la question de
    # l'artiste est « où en sont mes nouveautés », pas le classement de tout le catalogue.
    from ._release_targets import (MAX_TRACKS, by_proximity, indicators_figure,
                                   last_releases, track_levers, values_figure)
    choix = st.multiselect(
        t("trigger_algo.cat.releases", "🎵 Tes dernières sorties (5 au plus)"),
        options=list(df["song"]), default=last_releases(df),
        key=f"cat_compare_{artist_id}",
        help=t("trigger_algo.cat.releases_help",
               "Tes cinq sorties les plus récentes sont choisies d'office ; remplace-les "
               "par d'autres titres pour les comparer."))
    # The cap is applied HERE, not by `max_selections`: Streamlit RAISES when the session
    # already holds more (this key served the uncapped selector before R247), and a
    # widened filter crashed the tab (test_a_widened_filter_still_renders).
    if len(choix) > MAX_TRACKS:
        st.caption(t("trigger_algo.cat.releases_cut",
                     "Les {n} premiers titres choisis sont montrés.").format(n=MAX_TRACKS))
        choix = choix[:MAX_TRACKS]
    if choix:
        df = df[df["song"].isin(choix)].reset_index(drop=True)
    feats_of = {r["song"]: _feats_json(r.get("features_json")) for r in lignes.to_dict("records")}
    levers = {s_: track_levers(feats_of.get(s_, {})) for s_ in choix}

    avec_porte = df[df["avancement"].notna()]

    # ── Trois tuiles ────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    c1.metric(t("trigger_algo.cat.tile_active", "Titres avec un levier"),
              f"{len(avec_porte)}/{len(df)}",
              help=t("trigger_algo.cat.tile_active_help",
                     "Titres dont au moins une métrique mesurée est sous son "
                     "objectif — c'est là qu'une action change quelque chose."))
    if not avec_porte.empty:
        tete = avec_porte.iloc[0]
        c2.metric(t("trigger_algo.cat.tile_closest", "Le plus proche d'une porte"),
                  str(tete["song"])[:24],
                  delta=f"{tete['gate_label']} : il manque "
                        f"{tete['gate_gap']:,.0f} {tete['gate_unit']}".replace(",", " "),
                  delta_color="off")
        c3.metric(t("trigger_algo.cat.tile_progress", "Son avancement"),
                  f"{tete['avancement']:.0%}",
                  help=t("trigger_algo.cat.tile_progress_help",
                         "Où il en est sur ce levier précis, pas sa chance globale."))

    # ── R247 (fiche 42) — deux figures, dans l'ordre de la question ──────────
    if choix:
        st.markdown(t("trigger_algo.cat.gauges_head",
                      "**Où chaque titre en est, algorithme par algorithme** — le chemin "
                      "le plus court : le levier le plus proche de la valeur où le modèle "
                      "passe à 80 % de chances."))
        charts.plotly_chart(indicators_figure(by_proximity(choix, levers), levers),
                            width="stretch")
        _render_next_steps(db, artist_id, choix, feats_of)
        st.markdown(t("trigger_algo.cat.values_head",
                      "**Les valeurs qui déclencheraient** — ta valeur (barre) et, pour "
                      "chaque algorithme, la valeur visée (trait). Trait vif : calculée par "
                      "le modèle pour CE titre ; trait pâle : un repère général, là où le "
                      "modèle n'atteint jamais 80 %."))
        charts.plotly_chart(values_figure(choix, levers), width="stretch")
        st.caption(t("trigger_algo.cat.gauges_note",
                     "Pourquoi pas le pourcentage de chances directement : sur ton catalogue, "
                     "il ne varie que de quelques centièmes de point d'un titre à l'autre (il "
                     "est posé sur le plancher de la calibration) — il ne dirait rien. Le "
                     "chemin parcouru, lui, bouge quand tu agis."))

    # ── Les leviers d'artiste, UNE fois ─────────────────────────────────────
    artiste = leviers_artiste(df)
    if artiste:
        lignes_txt = " · ".join(
            f"**{a['label']}** {a['current']:,.0f}/{a['target']:,.0f} {a['unit']}"
            .replace(",", " ") for a in artiste[:3])
        st.info(t("trigger_algo.cat.artist_levers",
                  "🎤 **Vrai pour tout ton catalogue** (ces leviers sont les mêmes "
                  "sur chaque titre) : {levers}").format(levers=lignes_txt))

    # ── Le tableau comparatif ───────────────────────────────────────────────
    _render_table(df)


def _render_table(df: pd.DataFrame) -> None:
    """La comparaison titre par titre. Les probabilités viennent EN DERNIER."""
    aff = pd.DataFrame({
        t("trigger_algo.cat.col_track", "Titre"): df["song"],
        t("trigger_algo.cat.col_age", "Âge"): [_age(v) for v in df["days_since_release"]],
        t("trigger_algo.cat.col_gate", "Porte la plus proche"): df["gate_algo"],
        t("trigger_algo.cat.col_missing", "Il me manque"): [
            "—" if pd.isna(g) else f"{g:,.0f} {u}".replace(",", " ")
            for g, u in zip(df["gate_gap"], df["gate_unit"])],
        t("trigger_algo.cat.col_progress", "Avancement"): df["avancement"],
        t("trigger_algo.cat.col_levers", "Leviers restants"): df["n_leviers"],
        t("trigger_algo.cat.col_saves", "Saves 28j"): df["saves_28d"],
        t("trigger_algo.cat.col_adds", "Ajouts playlist 28j"): df["adds_28d"],
        t("trigger_algo.cat.col_streams", "Streams 28j"): df["streams_28d"],
        # DW → Radio → RR, the one order (`ALGO_ORDER`, R380).
        "DW %": [_proba("dw", v) for v in df["dw_probability"]],
        "Radio %": [_proba("radio", v) for v in df["radio_probability"]],
        "RR %": [_proba("rr", v) for v in df["rr_probability"]],
    })
    st.dataframe(
        aff, hide_index=True, width="stretch",
        column_config={
            t("trigger_algo.cat.col_progress", "Avancement"):
                st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=1),
        },
    )
    st.caption(t(
        "trigger_algo.cat.table_note",
        "⚠️ **« pas d'estimation fiable »** remplace une probabilité dont le score "
        "brut est négligeable : le modèle n'a pas tranché pour ce titre, il n'hésite "
        "pas, et ce chiffre ne distinguerait rien — c'est pourquoi il n'est pas "
        "affiché, et pourquoi le tableau est trié sur l'avancement."))


def _proba(algo: str, valeur) -> str:
    """REFUSE, not mark (2026-09-26): one policy for every surface — the shared door."""
    return format_proba(algo, valeur, decimals=1)


def _render_next_steps(db, artist_id, tracks: list[str], feats_of: dict) -> None:
    """R263 — under the gauges: per track, the next step and what it is worth in €.

    Budget: one `pareto` per track priced on its FIRST lever only (2 model calls), and
    one gate-value read per track — five tracks at most, so ≤ 10 model calls.
    """
    import pandas as pd
    from src.dashboard.utils import formats
    from src.dashboard.utils.formats import eur, num
    from ._pareto import next_step_rows, pareto
    from ._tab_titre import _NOMS, _valeur_de, _valeur_porte
    from src.dashboard.utils.algo_knowledge import nearest_gate

    plans = []
    for song in tracks:
        feats = feats_of.get(song) or {}
        porte = nearest_gate(feats)
        if not porte:
            continue
        valeurs, _, _ = _valeur_porte(db, artist_id, song)
        valeur = _valeur_de(valeurs, porte["algo"])
        plans.append((song, pareto(feats, valeur_porte=valeur, chiffrer=1), valeur))
    rows = next_step_rows(plans)
    if not rows:
        return
    st.markdown(t("trigger_algo.cat.next_head",
                  "**Le prochain geste, titre par titre** — la porte la plus proche, le "
                  "levier le moins coûteux pour s'en approcher, et ce qu'il rapporte."))
    formats.table(pd.DataFrame({
        t("trigger_algo.cat.next_track", "Titre"): [r["song"] for r in rows],
        t("trigger_algo.cat.next_gate", "Porte"): [_NOMS.get(r["algo"], r["algo"]) for r in rows],
        t("trigger_algo.cat.next_lever", "Levier"): [r["lever"] for r in rows],
        t("trigger_algo.cat.col_from_to", "Aujourd'hui → objectif"): [
            f"{num(r['current'], 0)} → {num(r['target'], 0)} {r['unit']}" for r in rows],
        t("trigger_algo.cat.col_gate_eur", "La porte vaut"): [eur(r["gate_eur"], 0) for r in rows],
        t("trigger_algo.cat.col_step_eur", "Ce geste rapporte"): [
            "—" if r["step_eur"] is None else "+" + eur(r["step_eur"], 2) for r in rows],
    }))
