"""🔓 Aperçu : déclencher les algos — ce que Road to Algo fait, pour ta dernière sortie. GRATUIT.

Type: Feature
Uses: view_session, algo_preview_data (load_ml_pred, sur_le_plancher, cout_par_stream,
      budget_pour_streams), algo_knowledge (split_coach_actions), artist_cashflow
      (trigger_value, track_stream_rate), plan_gate.bouton_vers, i18n
Depends on: ml_song_predictions, v_meta_daily, v_s4a_song_daily
Persists in: — (lecture seule)

R193 (2026-09-26), décision du propriétaire : « tes données sont gratuites, les prédictions
sont payantes » (ADR-029) — et un APERÇU gratuit qui montre la valeur ajoutée de Road to
Algo : les actions à faire et le budget pour déclencher les algos. Placé juste au-dessus de
la page payante, avec un cadenas OUVERT vert.

CE QU'IL MONTRE, ET CE QU'IL REFUSE DE MONTRER (code-critic, même jour)
- La porte la plus proche par algorithme et l'ÉCART à combler, avec le levier — c'est ce
  que le modèle sait vraiment dire aujourd'hui (`split_coach_actions`, zones mesurées).
- **Aucun pourcentage tant que la probabilité est au plancher du calibrage** : en
  production le 2026-09-26, TOUTES le sont. Un visiteur sans contexte lit un chiffre comme
  vrai ; la page dit « pas encore d'estimation fiable » à la place.
- Le budget est un ORDRE DE GRANDEUR (coût par stream agrégé sur tous les titres ×
  écart de streams 7 j — le même chemin que le panneau Premium, un seul chiffre par titre),
  et la page le dit. Sans dépense Meta, pas de chiffre : dit aussi.
- L'état vide (aucune prédiction) sera le cas le plus fréquent tant que l'activation n'est
  pas réglée (ADR-028) : il nomme le geste qui le lève.
"""
from __future__ import annotations

import datetime as dt

import streamlit as st

from src.dashboard.utils import view_session
from src.dashboard.utils.algo_knowledge import split_coach_actions
from src.dashboard.utils.algo_preview_data import (
    budget_pour_streams, cout_par_stream, load_ml_pred, sur_le_plancher)
from src.dashboard.utils.i18n import t
from src.dashboard.utils.plan_gate import bouton_vers

_ALGOS = (("DW", "Discover Weekly", "dw_probability"),
          ("RR", "Release Radar", "rr_probability"),
          ("RADIO", "Radio", "radio_probability"))
_COST_WINDOW_DAYS = 90


def _n(x) -> str:
    """A number with a thin space for thousands — formatted ALONE, never by replacing the
    commas of a whole sentence (that ate « médiane de la cohorte, pas un gain garanti »)."""
    return f"{float(x or 0):,.0f}".replace(",", "\u202f")


def compose(pred: dict | None, feats: dict, eur_per_stream: float | None,
            worth: dict[str, float]) -> dict:
    """Everything the page shows, as data. Pure.

    `pred`: latest ml_song_predictions row (or None); `feats`: its features_json;
    `eur_per_stream`: ad cost per stream over the window (None without Meta spend);
    `worth`: {algo code: € value of a trigger}. Returns per-algo rows and ONE budget."""
    rows, gaps = [], []
    for code, name, col in _ALGOS:
        proba = (pred or {}).get(col)
        reliable = proba is not None and not sur_le_plancher(code.lower(), proba)
        track, _artist = split_coach_actions(code, feats) if feats else ([], [])
        first = track[0] if track else None
        for a in track:
            if a.get("feature") == "StreamsLast7Days" and a.get("gap"):
                gaps.append(float(a["gap"]))
        rows.append({
            "code": code, "name": name,
            "proba": float(proba) if reliable else None,
            "next": first,
            "worth": worth.get(code),
        })
    gap = max(gaps) if gaps else None
    return {"rows": rows, "streams_gap": gap,
            "budget": budget_pour_streams(gap, eur_per_stream) if gap is not None else None}


def _latest_scored_song(db, artist_id):
    rows = db.fetch_query(
        "SELECT DISTINCT ON (song) song, days_since_release FROM ml_song_predictions "
        "WHERE artist_id = %s ORDER BY song, prediction_date DESC", (artist_id,))
    rows = [r for r in (rows or []) if r[1] is not None]
    return min(rows, key=lambda r: r[1])[0] if rows else None


def _worth(db, artist_id, song) -> dict[str, float]:
    from src.dashboard.utils.artist_cashflow import track_stream_rate, trigger_value
    try:
        rate = (track_stream_rate(db, artist_id, song) or {}).get("eur_par_stream")
        df = trigger_value(db, rate) if rate else None
    except Exception:  # noqa: BLE001 — a missing worth hides one line, not the page
        return {}
    if df is None or df.empty:
        return {}
    return {r["algo"]: float(r["valeur_eur"]) for _, r in df.iterrows()}


def show() -> None:
    with view_session() as (db, artist_id):
        st.subheader(t("algo_preview.title", "🔓 Aperçu : déclencher les algos Spotify"))
        song = _latest_scored_song(db, artist_id) if artist_id else None
        if song is None:
            st.info(t("trigger_algo.cat.empty",
                      "**Ton catalogue n'a pas encore été noté.** Le calcul tourne chaque "
                      "nuit dès qu'un titre a au moins une écoute sur les 35 derniers "
                      "jours. Il lui faut tes données Spotify for Artists : dépose-les "
                      "sur la page **📝 Saisie S4A**."))
            return
        st.caption(t("algo_preview.intro",
                     "Ta dernière sortie, **{song}** — ce que Road to Algo calcule pour "
                     "elle. Premium le fait pour tout ton catalogue, avec les simulations "
                     "et le budget détaillé.").format(song=song))
        pred = load_ml_pred(db, song, artist_id)
        from src.dashboard.views.trigger_algo._catalogue import _feats
        today = dt.date.today()
        view = compose(pred, _feats((pred or {}).get("features_json")),
                       cout_par_stream(db, artist_id,
                                       today - dt.timedelta(days=_COST_WINDOW_DAYS), today),
                       _worth(db, artist_id, song))

        cols = st.columns(3)
        for col, row in zip(cols, view["rows"]):
            with col:
                st.markdown(f"##### {row['name']}")
                if row["proba"] is None:
                    st.markdown(t("algo_preview.no_estimate",
                                  "Chance de déclencher : *pas encore d'estimation fiable*"))
                else:
                    st.markdown(t("algo_preview.estimate", "Chance de déclencher : **{p:.0%}**")
                                .format(p=row["proba"]))
                a = row["next"]
                if a:
                    st.markdown(t("algo_preview.next",
                                  "**À faire** : {label} — {cur} sur {tgt} {unit}.")
                                .format(label=a["label"], cur=_n(a["current"]),
                                        tgt=_n(a["target"]), unit=a.get("unit", "")))
                    st.caption(a.get("lever", ""))
                else:
                    st.markdown(t("algo_preview.nothing_left",
                                  "Rien dans la zone de pénalité pour cet algorithme."))
                if row["worth"]:
                    st.caption(t("algo_preview.worth",
                                 "Une entrée dans {name} vaut ≈ **{w} €** (médiane de "
                                 "la cohorte, pas un gain garanti).")
                               .format(name=row["name"], w=_n(row["worth"])))

        st.markdown("---")
        if view["budget"] is not None and view["streams_gap"]:
            st.markdown(t("algo_preview.budget",
                          "💶 Pour combler l'écart de **{g} streams sur 7 jours** : "
                          "**≈ {b} € de pub**.")
                        .format(g=_n(view["streams_gap"]), b=_n(view["budget"])))
            st.caption(t("trigger_algo.reg.budget_caveat",
                         "Ordre de grandeur, pas un devis : le coût d'un stream est "
                         "agrégé sur toutes tes campagnes et tous tes titres."))
        elif view["streams_gap"]:
            st.caption(t("algo_preview.no_cost",
                         "Pas de dépense Meta sur les 90 derniers jours : impossible "
                         "d'estimer ce que coûte un stream, donc le budget."))
        bouton_vers("trigger_algo",
                    ouvert=t("algo_preview.open", "🚀 Ouvrir Road to Algo"),
                    ferme=t("algo_preview.upgrade",
                            "🔒 Tout le catalogue, les simulations et le budget détaillé "
                            "→ Premium"),
                    key="algo_preview_cta", type="primary")
