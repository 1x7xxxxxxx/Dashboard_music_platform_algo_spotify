"""Inférence ML pour le scoring quotidien des chansons.

Charge les modèles XGBoost depuis machine_learning/mlruns/ et prédit:
- dw_probability  : probabilité d'être propulsé en Discover Weekly
- rr_probability  : probabilité d'être propulsé en Release Radar
- radio_probability: probabilité d'être propulsé en Radio Spotify

Remarque : les modèles ont été entraînés avec StandardScaler. Ce module
applique uniquement les transformations log (critiques), sans scaling.
Les probabilités sont donc indicatives (comparaison relative entre chansons),
pas des probabilités absolues calibrées.
"""
import os
import logging
from statistics import median

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chemins vers les meilleurs modèles (dernier run par expérience)
# Résolu à l'exécution pour supporter Airflow (/opt/airflow/) et local.
# ---------------------------------------------------------------------------
_MLRUNS_DIR = os.environ.get(
    "ML_MODELS_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "machine_learning", "mlruns")
)

MODEL_PATHS = {
    "dw_classifier":    "2/models/m-5487d6f842b84d099659332045aad1db/artifacts/model.ubj",
    "radio_classifier": "3/models/m-77b18d0a6bfc458891e39128d1ee11d1/artifacts/model.ubj",
    "rr_classifier":    "4/models/m-6331266b24604c65b1494a798b0be03d/artifacts/model.ubj",
    "dw_regressor":     "5/models/m-3e9e570baa7348bfb504d698d9084d1b/artifacts/model.ubj",
    "rr_regressor":     "7/models/m-e8b2e7dce68e4759832f7261dc59955f/artifacts/model.ubj",
    "radio_regressor":  "6/models/m-3eb19b69b4344356819433eb63d7d978/artifacts/model.ubj",
}

# Ordre des features attendu par les modèles (issu du notebook)
FEATURE_COLUMNS = [
    "StreamsLast7Days_log",
    "CurrentSpotifyFollowers_log",
    "HowManySongsDoYouHaveInRadioRightNow",
    "HowManySongsHasThisArtistEverReleased",
    "IsThisSongOptedIntoSpotifyDiscoveryMode",
    "ReleaseConsistencyNum",
    "DaysSinceRelease",
    "NonAlgoStreams28Days_log",
    "ListenersStreamRatio28Days_adj",
    "SavesLast28Days_adj",
    "PlaylistAddsLast28Days_adj",
    "ReleasePhaseEarly",
    "Velocity_Streams",
]

MODEL_VERSION = "v1_noscaler"

_model_cache = {}


def _resolve_path(relative_path: str) -> str:
    """Résout le chemin absolu vers un modèle."""
    base = os.path.abspath(_MLRUNS_DIR)
    return os.path.join(base, relative_path)


def load_model(model_key: str):
    """Charge (et met en cache) un modèle XGBoost depuis le disque."""
    if model_key in _model_cache:
        return _model_cache[model_key]

    try:
        import xgboost as xgb
    except ImportError:
        raise RuntimeError("xgboost non installé — `pip install xgboost>=2.0.0`")

    if model_key not in MODEL_PATHS:
        raise ValueError(f"Modèle inconnu: {model_key}. Disponibles: {list(MODEL_PATHS)}")

    path = _resolve_path(MODEL_PATHS[model_key])
    if not os.path.exists(path):
        raise FileNotFoundError(f"Modèle introuvable: {path}")

    if "classifier" in model_key:
        model = xgb.XGBClassifier()
    else:
        model = xgb.XGBRegressor()

    model.load_model(path)
    _model_cache[model_key] = model
    logger.info(f"Modèle chargé: {model_key} depuis {path}")
    return model


def build_features(db, artist_id: int, song: str) -> dict:
    """Construit le vecteur de features pour une chanson depuis la DB.

    Calculées depuis la DB : streams, followers, catalogue, vélocité,
    DaysSinceRelease, ratio écoutes/auditeur (streams par auditeur, aligné sur
    l'entraînement), Saves (s4a_songs_global), PlaylistAdds
    (s4a_song_playlist_adds), ReleaseConsistency (cadence médiane des sorties).
    Encore imputées faute de source : NonAlgoStreams28Days (split par source —
    Phase 2), HowManySongsDoYouHaveInRadioRightNow, DiscoveryMode (API S4A).

    Returns:
        dict avec les 13 features + raw values pour stockage dans features_json.
    """
    # --- Streams last 7 / 28 days ---
    row = db.fetch_query(
        """
        SELECT
            COALESCE(SUM(CASE WHEN date >= CURRENT_DATE - 7 THEN streams ELSE 0 END), 0) AS s7,
            COALESCE(SUM(CASE WHEN date >= CURRENT_DATE - 28 THEN streams ELSE 0 END), 0) AS s28,
            COALESCE(SUM(CASE WHEN date >= CURRENT_DATE - 35 AND date < CURRENT_DATE - 7 THEN streams ELSE 0 END), 0) AS s_prev21,
            MIN(date) AS first_date
        FROM s4a_song_timeline
        WHERE artist_id = %s AND song = %s
          AND song NOT ILIKE '%%1x7xxxxxxx%%'
        """,
        (artist_id, song)
    )
    if not row or row[0][0] is None:
        return {}

    s7, s28, s_prev21, first_date = row[0]
    s7, s28, s_prev21 = int(s7 or 0), int(s28 or 0), int(s_prev21 or 0)

    # DaysSinceRelease
    days_since = 0
    if first_date:
        from datetime import date
        delta = date.today() - first_date
        days_since = max(0, delta.days)

    # Velocity : (avg last 7d) / (avg prior 21d) — clipped [0, 5]
    avg_7d = s7 / 7.0
    avg_prior = s_prev21 / 21.0 if s_prev21 > 0 else 0
    if avg_prior > 0:
        velocity = min(avg_7d / avg_prior, 5.0)
    elif avg_7d > 0:
        velocity = 5.0
    else:
        velocity = 1.0
    velocity = max(0.0, velocity)

    # --- Followers (last known) ---
    aud = db.fetch_query(
        "SELECT followers FROM s4a_audience WHERE artist_id = %s ORDER BY date DESC LIMIT 1",
        (artist_id,)
    )
    followers = int(aud[0][0]) if aud and aud[0][0] else 0

    # --- Catalog size ---
    catalog = db.fetch_query(
        "SELECT COUNT(DISTINCT song) FROM s4a_songs_global WHERE artist_id = %s AND time_window = '12m'",
        (artist_id,)
    )
    n_songs = int(catalog[0][0]) if catalog else 1

    # --- Song snapshot (listeners / streams / saves) ---
    # Prefer the '28d' window (matches the *28Days features); fall back to '12m'.
    global_row = db.fetch_query(
        """SELECT listeners, streams, saves
           FROM s4a_songs_global
           WHERE artist_id = %s AND song = %s AND time_window IN ('28d', '12m')
           ORDER BY CASE time_window WHEN '28d' THEN 0 ELSE 1 END
           LIMIT 1""",
        (artist_id, song)
    )
    listeners_global = int(global_row[0][0]) if global_row and global_row[0][0] else 0
    streams_global = int(global_row[0][1]) if global_row and global_row[0][1] else 0
    saves_28d = int(global_row[0][2]) if global_row and global_row[0][2] else 0
    # Streams per listener — training sweet-spot 2.2-4. Was inverted AND clamped
    # to 1.0 (listeners/streams), so the live feature could never reach its bonus
    # zone; realigned with the training definition.
    ratio = streams_global / listeners_global if listeners_global > 0 else 0.0

    # --- Playlist adds (last 28 days) from manual S4A entries ---
    pa_row = db.fetch_query(
        """SELECT COALESCE(SUM(count), 0) FROM s4a_song_playlist_adds
           WHERE artist_id = %s AND song = %s AND recorded_at >= CURRENT_DATE - 28""",
        (artist_id, song)
    )
    playlist_adds_28d = int(pa_row[0][0]) if pa_row and pa_row[0][0] else 0

    # --- Release consistency: median weeks between successive releases ---
    # Source = real release dates (track_release_reference, per-tenant). The
    # timeline first-appearance is NOT usable here: history is backfilled in one
    # import so every song shares the same first date. Neutral 0.5 only when
    # there are < 2 distinct release dates to measure a cadence.
    rel_rows = db.fetch_query(
        """SELECT release_date FROM track_release_reference
           WHERE artist_id = %s AND release_date IS NOT NULL""",
        (artist_id,)
    )
    rel_dates = sorted({r[0] for r in (rel_rows or []) if r[0]})
    if len(rel_dates) >= 2:
        gaps = [(rel_dates[i] - rel_dates[i - 1]).days / 7.0 for i in range(1, len(rel_dates))]
        release_consistency = float(median(gaps))
    else:
        release_consistency = 0.5

    features = {
        "StreamsLast7Days_log": float(np.log1p(s7)),
        "CurrentSpotifyFollowers_log": float(np.log1p(followers)),
        "HowManySongsDoYouHaveInRadioRightNow": 0.0,   # non disponible (pas de source)
        "HowManySongsHasThisArtistEverReleased": float(n_songs),
        "IsThisSongOptedIntoSpotifyDiscoveryMode": 0.0,  # non disponible (API S4A)
        "ReleaseConsistencyNum": float(release_consistency),
        "DaysSinceRelease": float(days_since),
        "NonAlgoStreams28Days_log": 0.0,                 # non disponible (split par source — Phase 2)
        "ListenersStreamRatio28Days_adj": float(ratio),
        "SavesLast28Days_adj": float(saves_28d),
        "PlaylistAddsLast28Days_adj": float(playlist_adds_28d),
        "ReleasePhaseEarly": 1.0 if days_since < 30 else 0.0,
        "Velocity_Streams": float(velocity),
    }

    # Extra raw values pour features_json (non utilisés pour ML)
    features["_raw_streams_7d"] = s7
    features["_raw_streams_28d"] = s28
    features["_raw_followers"] = followers

    return features


def score_song(features: dict) -> dict:
    """Prédit les probabilités et forecasts pour une chanson.

    Args:
        features: dict retourné par build_features()

    Returns:
        dict avec dw_probability, rr_probability, radio_probability,
        dw_streams_forecast_7d, rr_streams_forecast_7d, radio_streams_forecast_7d.
        Retourne None si un modèle est indisponible.
    """
    # Construire le DataFrame dans l'ordre exact
    X = pd.DataFrame([[features.get(col, 0.0) for col in FEATURE_COLUMNS]],
                     columns=FEATURE_COLUMNS)

    try:
        dw_clf = load_model("dw_classifier")
        dw_prob = float(dw_clf.predict_proba(X)[0, 1])
    except Exception as e:
        logger.warning(f"DW classifier indisponible: {e}")
        dw_prob = None

    try:
        rr_clf = load_model("rr_classifier")
        rr_prob = float(rr_clf.predict_proba(X)[0, 1])
    except Exception as e:
        logger.warning(f"RR classifier indisponible: {e}")
        rr_prob = None

    try:
        radio_clf = load_model("radio_classifier")
        radio_prob = float(radio_clf.predict_proba(X)[0, 1])
    except Exception as e:
        logger.warning(f"Radio classifier indisponible: {e}")
        radio_prob = None

    try:
        dw_reg = load_model("dw_regressor")
        dw_forecast = max(0, int(dw_reg.predict(X)[0]))
    except Exception as e:
        logger.warning(f"DW regressor indisponible: {e}")
        dw_forecast = None

    try:
        rr_reg = load_model("rr_regressor")
        rr_forecast = max(0, int(rr_reg.predict(X)[0]))
    except Exception as e:
        logger.warning(f"RR regressor indisponible: {e}")
        rr_forecast = None

    try:
        radio_reg = load_model("radio_regressor")
        radio_forecast = max(0, int(radio_reg.predict(X)[0]))
    except Exception as e:
        logger.warning(f"Radio regressor indisponible: {e}")
        radio_forecast = None

    return {
        "dw_probability": dw_prob,
        "rr_probability": rr_prob,
        "radio_probability": radio_prob,
        "dw_streams_forecast_7d": dw_forecast,
        "rr_streams_forecast_7d": rr_forecast,
        "radio_streams_forecast_7d": radio_forecast,
    }


def score_all_songs(db, artist_id: int) -> list[dict]:
    """Calcule les prédictions pour toutes les chansons actives d'un artiste.

    Une chanson est "active" si elle a au moins 1 stream dans les 35 derniers jours.

    Returns:
        Liste de dicts prêts pour upsert dans ml_song_predictions.
    """
    import json
    from datetime import date

    active_songs = db.fetch_query(
        """
        SELECT DISTINCT song
        FROM s4a_song_timeline
        WHERE artist_id = %s
          AND date >= CURRENT_DATE - 35
          AND song NOT ILIKE '%%1x7xxxxxxx%%'
        ORDER BY song
        """,
        (artist_id,)
    )

    if not active_songs:
        logger.info(f"Aucune chanson active pour artist_id={artist_id}")
        return []

    results = []
    today = date.today()

    for (song,) in active_songs:
        try:
            features = build_features(db, artist_id, song)
            if not features:
                logger.warning(f"Features vides pour {song!r} — skip")
                continue

            predictions = score_song(features)

            # Préparer features_json (sans les clés _raw_* internes)
            features_clean = {k: v for k, v in features.items() if not k.startswith("_")}

            row = {
                "artist_id": artist_id,
                "song": song,
                "prediction_date": today,
                "days_since_release": int(features.get("DaysSinceRelease", 0)),
                "streams_7d": int(features.get("_raw_streams_7d", 0)),
                "streams_28d": int(features.get("_raw_streams_28d", 0)),
                "dw_probability": predictions.get("dw_probability"),
                "rr_probability": predictions.get("rr_probability"),
                "radio_probability": predictions.get("radio_probability"),
                "dw_streams_forecast_7d": predictions.get("dw_streams_forecast_7d"),
                "rr_streams_forecast_7d": predictions.get("rr_streams_forecast_7d"),
                "radio_streams_forecast_7d": predictions.get("radio_streams_forecast_7d"),
                "model_version": MODEL_VERSION,
                "features_json": json.dumps(features_clean),
            }
            results.append(row)
            logger.info(f"  {song!r}: DW={predictions.get('dw_probability', 'N/A'):.2f} "
                        f"RR={predictions.get('rr_probability', 'N/A'):.2f} "
                        f"Radio={predictions.get('radio_probability', 'N/A'):.2f}")

        except Exception as e:
            logger.error(f"Erreur scoring {song!r}: {e}")

    return results
