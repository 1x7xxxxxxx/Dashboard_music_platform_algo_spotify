"""trigger_algo loaders — move-only split of _common."""
import json

import pandas as pd
import streamlit as st

# Process-global caches for static artifacts (mirror ml_inference._model_cache).
# The explainability tab calls _load_xgb_model 4x per render and re-reads the JSON
# tables every render; without memoization each call re-deserialized from disk.
_xgb_booster_cache: dict = {}
_json_artifact_cache: dict = {}


def _load_ml_pred(db, track: str, artist_id) -> dict | None:
    try:
        if artist_id:
            rows = db.fetch_query(
                """SELECT dw_probability, rr_probability, radio_probability,
                          dw_streams_forecast_7d, rr_streams_forecast_7d,
                          radio_streams_forecast_7d, pi_forecast_7d,
                          prediction_date, model_version, features_json
                   FROM ml_song_predictions
                   WHERE artist_id = %s AND song = %s
                   ORDER BY prediction_date DESC LIMIT 1""",
                (artist_id, track)
            )
        else:
            rows = db.fetch_query(
                """SELECT dw_probability, rr_probability, radio_probability,
                          dw_streams_forecast_7d, rr_streams_forecast_7d,
                          radio_streams_forecast_7d, pi_forecast_7d,
                          prediction_date, model_version, features_json
                   FROM ml_song_predictions
                   WHERE song = %s
                   ORDER BY prediction_date DESC LIMIT 1""",
                (track,)
            )
        if rows:
            r = rows[0]
            return {
                "dw_probability": r[0], "rr_probability": r[1], "radio_probability": r[2],
                "dw_streams_forecast_7d": r[3], "rr_streams_forecast_7d": r[4],
                "radio_streams_forecast_7d": r[5], "pi_forecast_7d": r[6],
                "prediction_date": r[7], "model_version": r[8], "features_json": r[9],
            }
    except Exception:
        pass
    return None


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


def _compute_score_20(df: pd.DataFrame) -> pd.DataFrame:
    """Add score_20 column min-max scaled to /20 (best track = 20, worst = 0)."""
    dw = df["dw_probability"].fillna(0).astype(float)
    rr = df["rr_probability"].fillna(0).astype(float)
    radio = df["radio_probability"].fillna(0).astype(float)
    vel = df["velocity"].fillna(0).astype(float).clip(0, 5) / 5.0
    composite = 0.35 * dw + 0.35 * rr + 0.20 * radio + 0.10 * vel
    max_val = composite.max()
    min_val = composite.min()
    span = max_val - min_val
    df = df.copy()
    # Min-max stretch over the full 0-20 range. Degenerate catalogue (1 track or
    # all-equal composites) → span 0 → everyone gets 20.0 (no meaningful ranking).
    df["score_20"] = ((composite - min_val) / span * 20) if span > 0 else 20.0
    return df


@st.cache_data(ttl=60)
def _load_scored_tracks(_db, artist_id):
    """Latest-date scored tracks with score_20, sorted desc. None if empty.

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
    return _compute_score_20(df).sort_values("score_20", ascending=False)


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
