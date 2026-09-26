"""trigger_algo loaders — move-only split of _common."""
import json

import streamlit as st
from src.dashboard.utils.algo_preview_data import load_ml_pred as _load_ml_pred  # noqa: F401,E402 — moved (R193)

# Process-global caches for static artifacts (mirror ml_inference._model_cache).
# The explainability tab calls _load_xgb_model 4x per render and re-reads the JSON
# tables every render; without memoization each call re-deserialized from disk.
_xgb_booster_cache: dict = {}
_json_artifact_cache: dict = {}


def _load_json_artifact(filename: str) -> dict | None:
    """Load + memoize a static JSON artifact exported by machine_learning/train.py.
    Failures are not cached so a transient miss can recover on a later call."""
    if filename in _json_artifact_cache:
        return _json_artifact_cache[filename]
    try:
        from src.utils.ml_inference import _resolve_path
        with open(_resolve_path(filename), encoding="utf-8") as f:
            data = json.load(f)
        _json_artifact_cache[filename] = data
        return data
    except Exception:
        return None


def _load_threshold_tables() -> dict | None:
    """PI-bracket trigger probabilities exported by machine_learning/train.py."""
    return _load_json_artifact("threshold_tables.json")


def _load_feature_importance() -> dict | None:
    """Gain-based feature importance per algo, exported by machine_learning/train.py."""
    return _load_json_artifact("feature_importance.json")


def _clean_feat(name: str) -> str:
    return (name.replace("_log", "").replace("_adj", "")
            .replace("Last28Days", " 28j").replace("Last7Days", " 7j"))


def _load_xgb_model(model_key: str):
    """Load and cache an XGBoost Booster from mlruns. Returns None if unavailable.
    Memoized per model_key (process-global); the explainability tab calls this 4x per
    render. Failures are not cached so a transient miss can recover."""
    if model_key in _xgb_booster_cache:
        return _xgb_booster_cache[model_key]
    try:
        import xgboost as xgb
        from src.utils.ml_inference import _resolve_path, MODEL_PATHS
        path = _resolve_path(MODEL_PATHS[model_key])
        model = xgb.Booster()
        model.load_model(path)
        _xgb_booster_cache[model_key] = model
        return model
    except Exception:
        return None


# ⚠️ `_compute_score_20` SUPPRIMÉ — 2026-09-22.
#
# Il calculait `0,35·DW + 0,35·RR + 0,20·Radio + 0,10·vélocité`, puis ÉTIRAIT le
# résultat en min-max sur une échelle de 0 à 20. Mesuré sur les dix titres de
# l'artiste 1 : l'écart de probabilité entre le meilleur et le pire vaut **0,36
# point**, et les dix sont posés sur le plancher de la calibration Platt. Le score
# transformait donc des fractions de point de bruit en un écart de vingt points —
# il fabriquait l'apparence d'un classement à partir d'une donnée qui n'en portait
# aucun, et c'était le nombre le plus trompeur de la vue.
#
# Remplacé partout — écran ET PDF, dans le même commit, pour ne pas laisser deux
# définitions du même chiffre survivre l'une à l'autre — par l'avancement vers la
# porte la plus proche (`views/trigger_algo/_catalogue.construire`), qui s'étale de
# 0,7 % à 98,9 % sur ces mêmes titres.
#
# Garde : `tests/test_a_calibrated_floor_is_not_a_ranking.py`.

@st.cache_data(ttl=60)
def _load_scored_tracks(_db, artist_id):
    """Les titres notés à la dernière date de prédiction. `None` si vide.

    ⚠️ Ne rend PLUS de `score_20` (supprimé le 2026-09-22, voir plus haut) et
    n'impose plus d'ordre : le classement du catalogue vit dans
    `views/trigger_algo/_catalogue.construire`, sur une grandeur qui sépare.

    Shared by the Vue Globale benchmark table and the Budget top-N% selector — called
    from 3 tabs that all render per rerun, so cached (ttl=60) to run the scan once.
    `_db` underscored → not hashed; keyed on artist_id.
    """
    cols = """song, dw_probability, rr_probability, radio_probability, streams_28d,
              CAST(features_json->>'Velocity_Streams' AS FLOAT) AS velocity"""
    try:
        if artist_id:
            df = _db.fetch_df(
                f"""SELECT {cols} FROM ml_song_predictions
                    WHERE artist_id = %s AND prediction_date = (
                        SELECT MAX(prediction_date) FROM ml_song_predictions WHERE artist_id = %s
                    )""",
                (artist_id, artist_id),
            )
        else:
            df = _db.fetch_df(
                f"""SELECT {cols} FROM ml_song_predictions
                    WHERE prediction_date = (SELECT MAX(prediction_date) FROM ml_song_predictions)"""
            )
    except Exception:
        return None
    if df is None or df.empty:
        return None
    return df


def _load_lifecycle_benchmark(_db, dataset_version="v2"):
    """Load the GLOBAL cohort lifecycle curves. `_db` underscored → not hashed.

    Prefers v2 (conditioned-on-trigger seed, migration 041 — meaningful medians +
    populated total_stream_median). Falls back to v1 when v2 is absent (migration not yet
    applied) so the tab never regresses to "benchmark indisponible".
    """
    def _fetch(version):
        return _db.fetch_df(
            """SELECT algorithm, age_week_bin, age_week_bin_order,
                      ratio_q1, ratio_median, ratio_q3,
                      total_stream_median, sample_count
               FROM algo_lifecycle_benchmark
               WHERE dataset_version = %s
               ORDER BY age_week_bin_order""",
            (version,),
        )
    try:
        df = _fetch(dataset_version)
        if (df is None or df.empty) and dataset_version != "v1":
            return _fetch("v1")
        return df
    except Exception:
        return None
