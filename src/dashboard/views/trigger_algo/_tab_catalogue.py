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
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.i18n import t
from src.dashboard.utils.semantic_colors import ATTENTION, BON, MAUVAIS, NEUTRE

from ._catalogue import construire, leviers_artiste, sur_le_plancher

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
    choix = st.multiselect(
        t("trigger_algo.cat.compare", "⚖️ Comparer des titres (vide = tout le catalogue)"),
        options=list(df["song"]), default=[], key=f"cat_compare_{artist_id}",
        help=t("trigger_algo.cat.compare_help",
               "Choisis-en deux ou trois pour ne garder qu'eux dans la figure et le "
               "tableau ci-dessous."))
    if choix:
        df = df[df["song"].isin(choix)].reset_index(drop=True)
        st.caption(t("trigger_algo.cat.compare_on",
                     "Comparaison sur **{n} titre(s)**. Vide le sélecteur pour "
                     "retrouver tout le catalogue.").format(n=len(df)))

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

    # ── La figure : l'avancement, titre par titre ───────────────────────────
    d = avec_porte.sort_values("avancement", ascending=True)
    if not d.empty:
        court = [s if len(str(s)) <= 34 else str(s)[:33] + "…" for s in d["song"]]
        fig = go.Figure(go.Bar(
            x=d["avancement"], y=court, orientation="h", showlegend=False,
            marker_color=[_teinte(v) for v in d["avancement"]],
            text=[f"{lab} · {g:,.0f} {u}".replace(",", " ")
                  for lab, g, u in zip(d["gate_label"], d["gate_gap"], d["gate_unit"])],
            textposition="outside", cliponaxis=False,
            hovertemplate="%{y}<br>%{x:.0%} · %{text}<extra></extra>"))
        fig.update_xaxes(tickformat=".0%", range=[0, 1.15])
        fig.update_layout(height=max(300, 42 * len(d) + 120), bargap=0.3,
                          margin={"l": 10, "r": 60, "t": 30, "b": 20})
        fig.update_yaxes(automargin=True)
        st.plotly_chart(fig, width="stretch")
        st.caption(t(
            "trigger_algo.cat.fig_note",
            "Chaque barre montre **le levier le plus proche de sa cible** pour ce "
            "titre, et ce qu'il lui manque. Le classement ne repose PAS sur la "
            "probabilité : entre ton meilleur et ton pire titre, elle ne varie que "
            "de quelques centièmes de point, parce qu'elle est posée sur le plancher "
            "de la calibration."))

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
        "DW %": [_proba("dw", v) for v in df["dw_probability"]],
        "RR %": [_proba("rr", v) for v in df["rr_probability"]],
        "Radio %": [_proba("radio", v) for v in df["radio_probability"]],
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
        "⚠️ **« ≈ plancher »** signale une probabilité dont le score brut est "
        "négligeable : le modèle n'a pas tranché pour ce titre, il n'hésite pas. "
        "Deux titres marqués ainsi ne se comparent pas entre eux — c'est pourquoi "
        "le tableau est trié sur l'avancement, pas sur ces colonnes."))


def _proba(algo: str, valeur) -> str:
    if valeur is None or pd.isna(valeur):
        return "—"
    marque = " ≈ plancher" if sur_le_plancher(algo, valeur) else ""
    return f"{float(valeur):.1%}{marque}"
