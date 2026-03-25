"""Vue admin : performances des modèles ML et prédictions récentes.

Admin uniquement — accessible via "🤖 Perf. Modèles ML" dans la navigation.
Affiche les artefacts MLflow (graphiques PNG) + tableau des scores en DB.
"""
import os
import streamlit as st
import pandas as pd
from pathlib import Path
from src.dashboard.utils import get_db_connection

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
        st.warning(f"Aucun artefact PNG trouvé pour ce run (`mlruns/{exp_id}/{run_id}/`).")
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
        st.error(f"Erreur lors de la récupération des prédictions : {e}")
        return

    if df.empty:
        st.info("Aucune prédiction en base. Lancez le DAG `ml_scoring_daily` pour générer les scores.")
        return

    st.write(f"**{len(df)} prédiction(s) trouvée(s)**")

    # Sélecteur de chanson pour filtrer
    songs = ["(toutes)"] + sorted(df["song"].unique().tolist())
    selected = st.selectbox("Filtrer par chanson", songs)
    if selected != "(toutes)":
        df = df[df["song"] == selected]

    # Formatage colonnes probabilités en %
    for col in ["dw_prob", "rr_prob", "radio_prob"]:
        if col in df.columns:
            df[col] = (df[col] * 100).round(1).astype(str) + "%"

    st.dataframe(df, width="stretch")


def show():
    # Admin uniquement
    if st.session_state.get("role") != "admin":
        st.error("⛔ Accès réservé aux administrateurs.")
        return

    st.title("🤖 Performance des Modèles ML")
    st.markdown("Artefacts MLflow des modèles actifs + suivi des scores en base de données.")

    db = get_db_connection()

    try:
        tab_labels = [label for _, _, label, _ in _MODELS] + ["🎯 Prédictions en DB"]
        tabs = st.tabs(tab_labels)

        for i, (exp_id, run_id, label, _) in enumerate(_MODELS):
            with tabs[i]:
                st.subheader(label)
                st.caption(f"Expérience MLflow n°{exp_id} — run `{run_id[:8]}…`")
                _show_model_tab(exp_id, run_id, label)

        with tabs[-1]:
            _show_predictions_tab(db)

    finally:
        db.close()
