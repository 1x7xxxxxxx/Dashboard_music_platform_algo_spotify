"""Vue admin : performances des modèles ML et prédictions récentes.

Admin uniquement — accessible via "🤖 Perf. Modèles ML" dans la navigation.
Affiche les artefacts MLflow (graphiques PNG) + tableau des scores en DB.
"""
import os
import streamlit as st
import pandas as pd
from pathlib import Path
from src.dashboard.utils import project_db, ml_widgets
from src.dashboard.utils.i18n import t
from src.dashboard.utils.algo_knowledge import ALGO_MODEL_METRICS, populated_algos

# ---------------------------------------------------------------------------
# Chemins artefacts (identiques à ml_inference.py)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_MLRUNS = Path(os.environ.get("ML_MODELS_PATH", str(_PROJECT_ROOT / "machine_learning" / "mlruns")))

# Modèles actifs : (exp_id, run_id, label, type)
_MODELS = [
    ("2", "070742d6839e489cac9ef738874b63e1", "Discover Weekly — Classifier", "classifier"),
    ("4", "49ceecf58bcf42b4a05b21f5163494e9", "Release Radar — Classifier", "classifier"),
    ("3", "3f1c8ca12a7f40669f60ff5ce4e3b3cf", "Radio Spotify — Classifier", "classifier"),
    ("5", "98d183115d0d4c56992bd1abf9e61fc6", "Discover Weekly — Regressor", "regressor"),
    ("7", "d0bdf95917684d8a87a2525b83e3245a", "Release Radar — Regressor", "regressor"),
    ("6", "16155f62fb45445eaf1c98dfd99fc4a3", "Radio Spotify — Regressor", "regressor"),  # pragma: allowlist secret
]


def _get_artifacts(exp_id: str, run_id: str) -> list[Path]:
    """Retourne les PNGs d'un run MLflow, triés par nom."""
    run_dir = _MLRUNS / exp_id / run_id / "artifacts"
    if not run_dir.exists():
        return []
    return sorted(run_dir.glob("*.png"))


def _show_model_tab(exp_id: str, run_id: str, label: str):
    """Affiche les artefacts PNG d'un modèle donné."""
    pngs = _get_artifacts(exp_id, run_id)
    if not pngs:
        st.warning(t("ml_performance.no_artifacts",
                     "Aucun artefact PNG trouvé pour ce run (`mlruns/{exp_id}/{run_id}/`).").format(
                         exp_id=exp_id, run_id=run_id))
        return
    for png in pngs:
        st.image(str(png), caption=png.stem.replace("_", " "), width="stretch")


def _show_predictions_tab(db):
    """Tableau des dernières prédictions depuis ml_song_predictions."""
    artist_id = st.session_state.get("artist_id")
    try:
        if artist_id:
            df = db.fetch_df(
                """SELECT song, prediction_date, model_version,
                          ROUND(dw_probability::numeric, 3) AS dw_prob,
                          ROUND(rr_probability::numeric, 3) AS rr_prob,
                          ROUND(radio_probability::numeric, 3) AS radio_prob,
                          dw_streams_forecast_7d, rr_streams_forecast_7d,
                          streams_7d, days_since_release
                   FROM ml_song_predictions
                   WHERE artist_id = %s
                   ORDER BY prediction_date DESC, song
                   LIMIT 100""",
                (artist_id,)
            )
        else:
            df = db.fetch_df(
                """SELECT a.name AS artist, p.song, p.prediction_date, p.model_version,
                          ROUND(p.dw_probability::numeric, 3) AS dw_prob,
                          ROUND(p.rr_probability::numeric, 3) AS rr_prob,
                          ROUND(p.radio_probability::numeric, 3) AS radio_prob,
                          p.dw_streams_forecast_7d, p.rr_streams_forecast_7d,
                          p.streams_7d, p.days_since_release
                   FROM ml_song_predictions p
                   LEFT JOIN saas_artists a ON p.artist_id = a.id
                   ORDER BY p.prediction_date DESC, p.song
                   LIMIT 200"""
            )
    except Exception as e:
        st.error(t("ml_performance.predictions_error",
                   "Erreur lors de la récupération des prédictions : {err}").format(err=e))
        return

    if df.empty:
        st.info(t("ml_performance.no_predictions",
                  "Aucune prédiction en base. Lancez le DAG `ml_scoring_daily` pour générer les scores."))
        return

    st.write(t("ml_performance.predictions_count",
               "**{count} prédiction(s) trouvée(s)**").format(count=len(df)))

    # Sélecteur de chanson — sortie la plus récente en haut (days_since_release asc).
    all_label = t("ml_performance.songs_all", "(toutes)")
    songs = [all_label] + (
        df.sort_values("days_since_release", ascending=True, na_position="last")
          ["song"].drop_duplicates().tolist()
    )
    selected = st.selectbox(t("ml_performance.filter_by_song", "Filtrer par chanson"), songs)
    if selected != all_label:
        df = df[df["song"] == selected]

    # Formatage colonnes probabilités en %. Postgres NUMERIC arrives as Decimal
    # (object dtype) → coerce to float first, else .round() raises "Expected
    # numeric dtype". NaN (NULL) is rendered as "—" rather than "nan%".
    for col in ["dw_prob", "rr_prob", "radio_prob"]:
        if col in df.columns:
            pct = (pd.to_numeric(df[col], errors="coerce") * 100).round(1)
            df[col] = pct.map(lambda v: f"{v}%" if pd.notna(v) else "—")

    st.dataframe(df, width="stretch")


def _show_scorecard_tab():
    """Classification scorecards (offline test-set metrics) per algorithm."""
    st.caption(t("ml_performance.scorecard_caption",
                 "Métriques d'évaluation hors-ligne (jeu de test). Source : analyse `machine_learning/`."))
    for algo in populated_algos():  # canonical order, single source of truth
        if algo in ALGO_MODEL_METRICS:
            ml_widgets.render_classification_scorecard(algo, compact=False)
            st.markdown("---")
        else:
            st.caption(t("ml_performance.scorecard_unavailable",
                         "{algo} : scorecard de classification non encore disponible.").format(algo=algo))


def show():
    # Admin uniquement
    if st.session_state.get("role") != "admin":
        st.error(t("ml_performance.access_denied", "⛔ Accès réservé aux administrateurs."))
        return

    st.title(t("ml_performance.title", "🤖 Performance des Modèles ML"))
    st.markdown(t("ml_performance.intro",
                  "Artefacts MLflow des modèles actifs + suivi des scores en base de données."))

    with project_db() as db:
        # ⚠️ DEUX ONGLETS RAPATRIÉS DE `trigger_algo` — 2026-09-22.
        #
        # « 📈 Modèle » (AUC, F1, rappel, actual-vs-predicted, résidus) et
        # « 🔍 Explainabilité » (cascades SHAP en log-odds, dérive, LIME) étaient
        # rendus dans la vue ARTISTE, vendue en Premium. Ils y exposaient un
        # vocabulaire de data-scientist — log-odds, R², drift, base_values — à
        # quelqu'un qui vient savoir quel titre pousser.
        #
        # Et sur les dix titres de production, la figure « actual vs predicted » est
        # **vide par construction** : `streams_7d = 0` et `dw_streams_forecast_7d`
        # est NULL sur les dix. Elle ne montrait rien à personne.
        #
        # Ce qui NE part PAS : le coach (`build_coach_actions`) et la sensibilité
        # locale, remontés en première ligne de l'onglet « Ce titre » — c'est le
        # cœur de ce qu'un artiste vient chercher.
        #
        # ⚠️ Les figures rapatriées vivent dans des blocs `with tabs[i]:` : cette
        # page n'a pas d'entrée dans `first-screen-ceilings.json`, donc son plafond
        # est le défaut de 5, et `_collapsed_lines` ne déplie pas un corps d'onglet.
        tab_labels = (
            [label for _, _, label, _ in _MODELS]
            + [t("ml_performance.tab_scorecard", "📋 Scorecard classification"),
               t("ml_performance.tab_reliability", "📈 Fiabilité par algo"),
               t("ml_performance.tab_explain", "🔍 Explainabilité (SHAP)"),
               t("ml_performance.tab_predictions", "🎯 Prédictions en DB")]
        )
        tabs = st.tabs(tab_labels)

        for i, (exp_id, run_id, label, _) in enumerate(_MODELS):
            with tabs[i]:
                st.subheader(label)
                st.caption(t("ml_performance.mlflow_experiment",
                             "Expérience MLflow n°{exp_id} — run `{run_id}…`").format(
                                 exp_id=exp_id, run_id=run_id[:8]))
                _show_model_tab(exp_id, run_id, label)

        with tabs[-4]:
            _show_scorecard_tab()

        with tabs[-3]:
            _show_reliability_tab(db)

        with tabs[-2]:
            _show_explainability_tab(db)

        with tabs[-1]:
            _show_predictions_tab(db)


def _choisir_titre(db, cle: str):
    """Le sélecteur de titre des deux onglets rapatriés — admin, tous locataires.

    La vue artiste bornait naturellement le choix à un locataire. Ici l'exploitant
    regarde le modèle, pas un compte : on lui laisse le catalogue entier, et le
    locataire du titre est porté par la requête de chaque onglet.
    """
    try:
        rows = db.fetch_query(
            "SELECT DISTINCT artist_id, song FROM ml_song_predictions "
            "ORDER BY artist_id, song")
    except Exception:                                    # noqa: BLE001
        return None, None
    if not rows:
        st.info(t("ml_performance.no_track",
                  "Aucune prédiction en base — rien à expliquer."))
        return None, None
    libelles = [f"#{a} · {s}" for a, s in rows]
    choix = st.selectbox(t("ml_performance.pick_track", "🎵 Titre"), libelles, key=cle)
    return rows[libelles.index(choix)]


def _show_reliability_tab(db) -> None:
    """Ce que valait « 📈 Modèle » dans la vue artiste."""
    from src.dashboard.views.trigger_algo._tab_model import _show_tab_model

    artist_id, song = _choisir_titre(db, "mlperf_fiab_track")
    if song:
        _show_tab_model(db, song, artist_id)


def _show_explainability_tab(db) -> None:
    """Ce que valait « 🔍 Explainabilité » — SHAP, dérive, LIME."""
    from src.dashboard.views.trigger_algo._common import _load_ml_pred
    from src.dashboard.views.trigger_algo._tab_explainability import (
        _show_tab_explainability,
    )

    artist_id, song = _choisir_titre(db, "mlperf_shap_track")
    if song:
        _show_tab_explainability(db, _load_ml_pred(db, song, artist_id), song, artist_id)
