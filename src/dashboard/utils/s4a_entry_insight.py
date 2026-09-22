"""Ce que la saisie S4A a produit — fraîcheur, complétude, et le pari du modèle.

Type: Sub
Uses: streamlit, pandas, plotly, src.dashboard.utils.semantic_colors
Depends on: s4a_song_playlist_adds, s4a_song_discovery_mode, s4a_song_nonalgo_streams,
  s4a_artist_radio_count, s4a_song_algo_outcomes, ml_song_predictions
Triggers: views/saisie_s4a.py (onglet « Ce que ça donne »)
Persists in: nothing

Pourquoi ces trois surfaces, et pas d'autres — MESURÉ EN PRODUCTION LE 2026-09-22
---------------------------------------------------------------------------------

La page de saisie affichait quatre grilles pré-remplies avec le dernier instantané.
Une grille remplie a exactement la même allure qu'on l'ait enregistrée hier ou il y a
cent jours. Relevé le 2026-09-22 sur la base de production :

======================================  ==========  ===============
table                                   lignes      dernière saisie
======================================  ==========  ===============
`s4a_song_algo_outcomes`                33          **2026-09-20**
`s4a_song_playlist_adds`                66          **2026-06-10**
`s4a_song_nonalgo_streams`              11          **2026-06-10**
`s4a_song_discovery_mode`               22          **2026-06-10**
`s4a_artist_radio_count`                **1**       **2026-06-10**
======================================  ==========  ===============

**Cent quatre jours** entre la moitié « signaux » et la moitié « résultats », et rien
à l'écran ne le disait. C'est la forme exacte de la classe déjà payée par R125 — une
table vide se lit comme « pas encore de données » — appliquée cette fois à la
péremption : une table PLEINE se lit comme « à jour ».

Le modèle lit ces valeurs comme si elles décrivaient aujourd'hui. Un compteur Radio
saisi une seule fois en juin alimente encore la prédiction de septembre.

Les trois surfaces répondent chacune à une question qu'on ne pouvait pas poser :

1. **Fraîcheur** — de quand date chaque bloc, et est-ce que ça compte encore ?
2. **Complétude** — quels titres n'ont jamais eu telle saisie ? Un titre absent
   n'apparaît nulle part ; seul un balayage par titre le rend visible.
3. **Le pari du modèle** — ce qu'il prédisait, et ce qui est arrivé. C'est la raison
   d'être de la saisie des résultats, et elle n'était visible sur aucun écran.

⚠️ **Ce que ces figures NE font PAS** : conclure. Au 2026-09-22 les onze titres
portent une probabilité prédite d'environ 7 % et **zéro** stream algorithmique
constaté. Sur onze titres à 7 %, l'espérance est de 0,8 déclenchement — observer zéro
est l'issue la plus probable, pas un démenti. La figure l'écrit ; elle ne calcule
aucun taux d'erreur, et c'est la même discipline que R147 sur les cohortes d'essai.
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.i18n import t
from src.dashboard.utils.semantic_colors import ATTENTION, BON, MAUVAIS, NEUTRE
from src.dashboard.utils.date_format import format_date

# Au-delà, une valeur ne décrit plus la situation d'aujourd'hui. 35 jours = la fenêtre
# de 28 jours de S4A plus une semaine de battement : on ne crie pas parce qu'une
# saisie mensuelle a trois jours de retard.
_PERIME_JOURS = 35
_TIEDE_JOURS = 14

_BLOCS = [
    ("s4a_song_playlist_adds", "Ajouts en playlist"),
    ("s4a_song_discovery_mode", "Discovery Mode"),
    ("s4a_song_nonalgo_streams", "Streams non-algo"),
    ("s4a_artist_radio_count", "Titres en Radio"),
    ("s4a_song_algo_outcomes", "Résultats réalisés"),
]


def _age_rows(db, artist_id: int) -> list[dict]:
    """Une ligne par bloc : dernière saisie et âge, ou l'absence DÉCLARÉE.

    Chaque table est interrogée séparément plutôt qu'en un `UNION ALL` construit
    par boucle : les noms viennent d'une constante du module, mais une f-string qui
    assemble cinq noms de table se relit mal et la règle transverse #8 demande de
    valider chaque nom. Ici la liste EST l'allowlist, et chaque requête la nomme.
    """
    today = _dt.date.today()
    out = []
    for table, libelle in _BLOCS:
        # ⚠️ Pas de `if table not in <allowlist>` ici, et c'est délibéré.
        # La première version en portait un — un `continue` qui ne pouvait JAMAIS
        # se déclencher, puisqu'on itère l'allowlist elle-même. Un contrôle mort qui
        # a l'apparence d'un garde est pire que pas de garde : il fait croire que la
        # question a été posée. `_BLOCS` EST la liste blanche de la règle transverse
        # #8 — un nom de table n'entre dans cette f-string que parce qu'il y figure.
        try:
            rows = db.fetch_query(
                f"SELECT MAX(recorded_at)::date, COUNT(*) FROM {table} "  # noqa: S608
                "WHERE artist_id = %s", (artist_id,))
        except Exception:                               # noqa: BLE001
            # Une table illisible n'est pas une table vide. On le DIT — c'est la
            # classe `une-erreur-avalée-devient-une-absence`, déjà payée ici.
            out.append({"bloc": libelle, "derniere": None, "lignes": None,
                        "jours": None, "illisible": True})
            continue
        derniere, n = (rows[0] if rows else (None, 0))
        jours = (today - derniere).days if derniere else None
        out.append({"bloc": libelle, "derniere": derniere, "lignes": int(n or 0),
                    "jours": jours, "illisible": False})
    return out


def _pastille(ligne: dict) -> str:
    if ligne["illisible"]:
        return "❓"
    if ligne["derniere"] is None:
        return "⬜"
    if ligne["jours"] >= _PERIME_JOURS:
        return "🔴"
    return "🟠" if ligne["jours"] >= _TIEDE_JOURS else "🟢"


def render_freshness(db, artist_id: int) -> None:
    """Quand chaque bloc a été saisi pour la dernière fois."""
    lignes = _age_rows(db, artist_id)
    st.subheader(t("s4a_insight.fresh_header", "🕐 Fraîcheur de tes saisies"))

    perimes = [ln for ln in lignes
               if not ln["illisible"] and ln["jours"] is not None
               and ln["jours"] >= _PERIME_JOURS]
    jamais = [ln for ln in lignes if not ln["illisible"] and ln["derniere"] is None]

    if perimes or jamais:
        st.warning(t(
            "s4a_insight.stale",
            "**{n} bloc(s) ne décrivent plus aujourd'hui.** Le modèle les lit pourtant "
            "comme s'ils étaient à jour : une valeur saisie une fois continue d'alimenter "
            "la prédiction de ce mois-ci."
        ).format(n=len(perimes) + len(jamais)))

    st.dataframe(pd.DataFrame([{
        "": _pastille(ln),
        t("s4a_insight.col_block", "Bloc"): ln["bloc"],
        t("s4a_insight.col_last", "Dernière saisie"): (
            "—" if ln["derniere"] is None else format_date(ln["derniere"])),
        t("s4a_insight.col_age", "Âge"): (
            "—" if ln["jours"] is None else f"{ln['jours']} j"),
        t("s4a_insight.col_rows", "Lignes"): (
            "?" if ln["lignes"] is None else ln["lignes"]),
    } for ln in lignes]), hide_index=True, width="stretch")
    st.caption(t("s4a_insight.fresh_legend",
                 "🟢 moins de {t} j · 🟠 moins de {p} j · 🔴 {p} j ou plus · "
                 "⬜ jamais saisi · ❓ table illisible").format(t=_TIEDE_JOURS, p=_PERIME_JOURS))


def render_completeness(db, artist_id: int, tracks: list[str]) -> None:
    """Quels titres n'ont JAMAIS eu telle saisie — un absent ne se voit pas seul."""
    st.subheader(t("s4a_insight.complete_header", "🧩 Titres couverts par la saisie"))
    if not tracks:
        st.info(t("s4a_insight.no_tracks", "Aucun titre à couvrir."))
        return

    def _songs(sql: str) -> set:
        try:
            return {r[0] for r in (db.fetch_query(sql, (artist_id,)) or [])}
        except Exception:                               # noqa: BLE001
            return set()

    adds = _songs("SELECT DISTINCT song FROM s4a_song_playlist_adds WHERE artist_id = %s")
    nonalgo = _songs("SELECT DISTINCT song FROM s4a_song_nonalgo_streams WHERE artist_id = %s")
    outcomes = _songs("SELECT DISTINCT song FROM s4a_song_algo_outcomes WHERE artist_id = %s")

    familles = [
        (t("s4a_insight.fam_adds", "Ajouts playlist"), adds),
        (t("s4a_insight.fam_nonalgo", "Streams non-algo"), nonalgo),
        (t("s4a_insight.fam_outcomes", "Résultats réalisés"), outcomes),
    ]
    st.dataframe(pd.DataFrame([
        {t("s4a_insight.col_track", "Titre"): s,
         **{nom: ("✅" if s in vus else "—") for nom, vus in familles}}
        for s in tracks
    ]), hide_index=True, width="stretch")

    manquants = [s for s in tracks if s not in outcomes]
    if manquants:
        st.caption(t(
            "s4a_insight.missing_outcomes",
            "**{n} titre(s) sur {tot}** n'ont aucun résultat réalisé saisi. Ce sont eux "
            "qui manquent au modèle pour apprendre — un titre sans résultat ne lui "
            "apprend rien, ni dans un sens ni dans l'autre."
        ).format(n=len(manquants), tot=len(tracks)))


def render_prediction_vs_reality(db, artist_id: int) -> None:
    """Ce que le modèle pariait, et ce qui est arrivé — avec l'effectif en face."""
    st.subheader(t("s4a_insight.bet_header", "🎲 Le pari du modèle, et ce qui est arrivé"))
    try:
        rows = db.fetch_query(
            """
            SELECT p.song,
                   p.dw_probability, p.rr_probability, p.radio_probability,
                   o.dw_streams, o.rr_streams, o.radio_streams
              FROM ml_song_predictions p
              JOIN LATERAL (
                   SELECT dw_streams, rr_streams, radio_streams
                     FROM s4a_song_algo_outcomes o2
                    WHERE o2.song = p.song AND o2.artist_id = p.artist_id
                      AND o2.time_window = '28d'
                    ORDER BY recorded_at DESC LIMIT 1
              ) o ON TRUE
             WHERE p.artist_id = %s
               AND p.prediction_date = (SELECT MAX(prediction_date)
                                          FROM ml_song_predictions WHERE artist_id = %s)
             ORDER BY p.dw_probability DESC
            """, (artist_id, artist_id))
    except Exception:                                   # noqa: BLE001
        st.info(t("s4a_insight.bet_unreadable",
                  "Comparaison indisponible : la table des prédictions n'a pas pu être lue. "
                  "Ce n'est pas « aucune prédiction »."))
        return

    if not rows:
        st.info(t("s4a_insight.bet_none",
                  "Aucun titre n'a À LA FOIS une prédiction et un résultat saisi. "
                  "Saisis les résultats réalisés (onglet précédent) pour que la "
                  "comparaison existe."))
        return

    d = pd.DataFrame(rows, columns=["song", "dw_p", "rr_p", "radio_p",
                                    "dw_s", "rr_s", "radio_s"])
    for c in ("dw_p", "rr_p", "radio_p", "dw_s", "rr_s", "radio_s"):
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0.0)
    d["proba_max"] = d[["dw_p", "rr_p", "radio_p"]].max(axis=1)
    d["streams"] = d["dw_s"] + d["rr_s"] + d["radio_s"]
    d = d.sort_values("proba_max", ascending=True)
    court = [s if len(s) <= 34 else s[:33] + "…" for s in d["song"]]

    # DEUX PANNEAUX, PAS DEUX SÉRIES SUR UN AXE. Une probabilité et un nombre de
    # streams n'ont ni la même unité ni le même ordre de grandeur ; le cliquet
    # d'axes secondaires de ce dépôt (`_MAX_SECONDARY_AXES = 0`) dit la même chose.
    from plotly.subplots import make_subplots
    fig = make_subplots(
        rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.08,
        subplot_titles=[t("s4a_insight.panel_pred", "Probabilité prédite"),
                        t("s4a_insight.panel_real", "Streams algo constatés (28 j)")])
    fig.add_trace(go.Bar(
        x=d["proba_max"], y=court, orientation="h", showlegend=False,
        marker_color=ATTENTION,
        text=[f"{v:.0%}" for v in d["proba_max"]], textposition="outside",
        cliponaxis=False,
        hovertemplate="%{y}<br>prédit : %{text}<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Bar(
        x=d["streams"], y=court, orientation="h", showlegend=False,
        marker_color=[BON if v > 0 else NEUTRE for v in d["streams"]],
        text=[f"{int(v):,}".replace(",", " ") for v in d["streams"]],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>constaté : %{text}<extra></extra>"), row=1, col=2)
    fig.update_xaxes(showticklabels=False)
    fig.update_layout(height=max(320, 42 * len(d) + 140), bargap=0.3,
                      margin={"l": 10, "r": 50, "t": 60, "b": 20})
    fig.update_yaxes(automargin=True)
    st.plotly_chart(fig, width="stretch")

    n = len(d)
    declenches = int((d["streams"] > 0).sum())
    attendu = float(d["proba_max"].sum())
    st.caption(t(
        "s4a_insight.bet_note",
        "**{d} titre(s) sur {n}** ont réellement déclenché un algorithme. Le modèle en "
        "attendait **{a:.1f}** sur cette sélection (somme des probabilités). Cet écart "
        "n'est PAS un taux d'erreur : sur un effectif de {n}, l'écart attendu par le "
        "seul hasard est du même ordre. La figure montre le pari, elle ne le juge pas."
    ).format(d=declenches, n=n, a=attendu))


def render_playlist_history(db, artist_id: int) -> None:
    """L'historique des ajouts en playlist — refusé s'il n'y a qu'un instantané."""
    st.subheader(t("s4a_insight.hist_header", "📈 Ajouts en playlist dans le temps"))
    try:
        rows = db.fetch_query(
            "SELECT recorded_at::date, time_window, SUM(count) "
            "FROM s4a_song_playlist_adds WHERE artist_id = %s "
            "AND time_window IN ('7d','28d','12m') "
            "GROUP BY 1, 2 ORDER BY 1", (artist_id,))
    except Exception:                                   # noqa: BLE001
        st.info(t("s4a_insight.hist_unreadable",
                  "Historique illisible — ce n'est pas « aucun historique »."))
        return
    if not rows:
        st.info(t("s4a_insight.hist_none", "Aucune saisie d'ajouts en playlist pour l'instant."))
        return

    d = pd.DataFrame(rows, columns=["jour", "fenetre", "total"])
    d["total"] = pd.to_numeric(d["total"], errors="coerce").fillna(0)
    jours = d["jour"].nunique()
    if jours < 2:
        # UNE COURBE À UN POINT N'EST PAS UNE COURBE. La tracer suggérerait une
        # tendance qu'un seul relevé ne peut pas porter — c'est la classe
        # `a-daily-figure-that-needs-consecutive-days`, déjà gardée ici.
        seul = d["jour"].iloc[0]
        st.info(t(
            "s4a_insight.hist_single",
            "Une seule saisie à ce jour ({d}) — il en faut deux pour dessiner une "
            "évolution. Les valeurs de cette saisie sont dans l'onglet **Signaux**."
        ).format(d=format_date(seul)))
        return

    couleurs = {"7d": NEUTRE, "28d": ATTENTION, "12m": MAUVAIS}
    noms = {"7d": "7 jours", "28d": "28 jours", "12m": "12 mois"}
    fig = go.Figure()
    for fen in ("7d", "28d", "12m"):
        part = d[d["fenetre"] == fen]
        if part.empty:
            continue
        fig.add_trace(go.Scatter(
            x=part["jour"], y=part["total"], name=noms[fen], mode="lines+markers",
            line={"color": couleurs[fen], "width": 2}, connectgaps=False))
    fig.update_layout(height=360, hovermode="x unified",
                      yaxis_title=t("s4a_insight.hist_axis", "Ajouts (tous titres)"),
                      margin={"t": 30})
    st.plotly_chart(fig, width="stretch")
    st.caption(t("s4a_insight.hist_note",
                 "Somme sur tous les titres, par date de saisie. Les trois fenêtres se "
                 "recouvrent — 28 jours CONTIENT 7 jours : elles ne s'additionnent pas."))
