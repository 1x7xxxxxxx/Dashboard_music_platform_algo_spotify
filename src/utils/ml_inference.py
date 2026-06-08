"""Inférence ML pour le scoring quotidien des chansons.

Charge les modèles XGBoost (v3) depuis machine_learning/models/ et prédit:
- dw_probability  : probabilité d'être propulsé en Discover Weekly
- rr_probability  : probabilité d'être propulsé en Release Radar
- radio_probability: probabilité d'être propulsé en Radio Spotify
- pi_forecast     : Popularity Index (0-100) prédit

Modèles v3 (machine_learning/analysis/03_train.py) : validés en group-CV par chanson
(StratifiedGroupKFold sur NameID), SANS SMOTE, calibration Platt ajustée hors-fold
(OOF) et non plus sur le test split. Les régresseurs de volume sont entraînés sur une
cible log1p — l'inférence applique donc expm1 (cf. _volume_forecast).
Contrat de features inchangé vs v2 (13 features). NOTE: NonAlgoStreams28Days_log et
HowManySongsDoYouHaveInRadioRightNow restent imputées à 0 faute de source live
(skew train/serve résiduel, levé en Phase 2 — l'UI affiche un avertissement).
"""
import os
import logging
from statistics import median

import numpy as np
import pandas as pd

from src.utils.track_matching import normalize_track_title

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chemins vers les meilleurs modèles (dernier run par expérience)
# Résolu à l'exécution pour supporter Airflow (/opt/airflow/) et local.
# ---------------------------------------------------------------------------
MODEL_VERSION = "v3"

_MODELS_DIR = os.environ.get(
    "ML_MODELS_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "machine_learning", "models", MODEL_VERSION)
)

MODEL_PATHS = {
    "dw_classifier":    "dw_classifier.ubj",
    "radio_classifier": "radio_classifier.ubj",
    "rr_classifier":    "rr_classifier.ubj",
    "dw_regressor":     "dw_regressor.ubj",
    "rr_regressor":     "rr_regressor.ubj",
    "radio_regressor":  "radio_regressor.ubj",
    "pi_regressor":     "pi_regressor.ubj",
    # Pre-release RR estimator: metadata-only (no streams), AUC 0.92. Served by
    # estimate_rr_prerelease() as a what-if planning tool, NOT by the daily scoring DAG.
    "rr_premiere_classifier": "rr_premiere_classifier.ubj",
}

# Serving contract for the pre-release estimator (= premiere.json["features"] order).
PREMIERE_FEATURE_COLUMNS = [
    "CurrentSpotifyFollowers_log",
    "HowManySongsHasThisArtistEverReleased",
    "IsThisSongOptedIntoSpotifyDiscoveryMode",
    "ReleaseConsistencyNum",
    "DaysSinceRelease",
    "ReleasePhaseEarly",
]

# Ordre des features attendu par les classifieurs/régresseurs de volume.
# DOIT rester strictement aligné sur machine_learning/train.py:FEATURE_COLUMNS.
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

# Features du régresseur PI (ordre exact de train.py:PI_FEATURES) — valeurs brutes.
PI_FEATURE_COLUMNS = [
    "ListenersLast28Days", "StreamsLast28Days", "SavesLast28Days",
    "PlaylistAddsLast28Days", "CurrentSpotifyFollowers", "DaysSinceRelease",
]

_model_cache = {}
_aux_cache = {}


def _resolve_path(relative_path: str) -> str:
    """Résout le chemin absolu vers un modèle."""
    base = os.path.abspath(_MODELS_DIR)
    return os.path.join(base, relative_path)


def _load_json(name: str) -> dict:
    """Charge (et met en cache) un JSON auxiliaire du dossier modèles. {} si absent."""
    if name not in _aux_cache:
        import json
        try:
            with open(_resolve_path(name), encoding="utf-8") as f:
                _aux_cache[name] = json.load(f)
        except (OSError, ValueError):
            _aux_cache[name] = {}
    return _aux_cache[name]


def _volume_forecast(model_key: str, X) -> int | None:
    """Volume forecast for a log-target regressor: expm1(pred), floored at 0.

    v3 regressors are trained on log1p(streams) (the raw target gives negative R²
    under honest group-CV). The model returns log space → invert with expm1. Returns
    None if the model is unavailable. The forecast is a conservative FLOOR, not a
    point estimate (all volume R² < 0.5 — see ALGO_REGRESSOR_METRICS).
    """
    try:
        reg = load_model(model_key)
        return max(0, int(np.expm1(reg.predict(X)[0])))
    except Exception as e:
        logger.warning(f"{model_key} indisponible: {e}")
        return None


def _calibrate(algo: str, p_raw):
    """Applique la calibration Platt (sigmoid) si disponible, sinon renvoie p_raw.

    calibrated = sigmoid(coef * p_raw + intercept) — voir machine_learning/train.py.
    Rend les probabilités directement interprétables (bandes 20/50% de la bannière
    verdict). Identité si calibration.json absent (rétro-compatible).
    """
    if p_raw is None:
        return None
    c = _load_json("calibration.json").get(algo)
    if not c:
        return float(p_raw)
    z = c["coef"] * float(p_raw) + c["intercept"]
    return float(1.0 / (1.0 + np.exp(-z)))


# Features excluded from drift detection. The first two are imputed to 0 (no live
# source yet — Phase 2), hence permanently out-of-distribution BY DESIGN. Discovery
# Mode now has a manual source (s4a_song_discovery_mode) but stays excluded because
# it is a bounded binary 0/1 flag — a z-score drift test on it is meaningless and
# would cry wolf whenever most songs are un-opted (0).
_IMPUTED_FEATURES = frozenset({
    "NonAlgoStreams28Days_log",
    "HowManySongsDoYouHaveInRadioRightNow",
    "IsThisSongOptedIntoSpotifyDiscoveryMode",
})


def check_drift(features: dict, z_max: float = 4.0) -> list:
    """Liste des features live hors de la distribution d'entraînement (|z| > z_max).

    Compare aux stats figées dans metrics.json (feature_stats). Monitoring : un
    modèle entraîné sur N=508 extrapole mal hors enveloppe. Les features imputées
    (Phase 2) sont exclues — toujours OOD par construction. Retourne [] si stats
    absentes ou tout en distribution.
    """
    stats = _load_json("metrics.json").get("feature_stats", {})
    drifted = []
    for col, s in stats.items():
        if col in _IMPUTED_FEATURES:
            continue
        val = features.get(col)
        std = s.get("std") or 0.0
        if val is None or std <= 0:
            continue
        if abs((float(val) - s["mean"]) / std) > z_max:
            drifted.append(col)
    return drifted


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
    (s4a_song_playlist_adds), DiscoveryMode (saisie manuelle —
    s4a_song_discovery_mode), ReleaseConsistency (cadence médiane des sorties).
    Encore imputées faute de source : NonAlgoStreams28Days (split par source —
    Phase 2), HowManySongsDoYouHaveInRadioRightNow.

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

    # DaysSinceRelease — prefer the authoritative per-song release date from
    # track_release_reference (matched on the normalized title). The timeline
    # MIN(date) is unreliable: history was backfilled in one import, so every song
    # shares the same first-appearance date. Fall back to the timeline first_date
    # only when no reference row matches this song.
    from datetime import date
    _ref = db.fetch_query(
        """SELECT release_date FROM track_release_reference
           WHERE artist_id = %s AND match_key = %s AND release_date IS NOT NULL
           LIMIT 1""",
        (artist_id, normalize_track_title(song)),
    )
    release_basis = (_ref[0][0] if _ref and _ref[0][0] else None) or first_date
    days_since = 0
    if release_basis:
        days_since = max(0, (date.today() - release_basis).days)

    # Velocity : (avg last 7d) / (avg prior 21d) — clipped [0, 5].
    # NOTE: must mirror the training feature engineering exactly (data_anon.csv
    # pipeline): no-prior-with-streams → 5.0, no-streams → 1.0. Changing this
    # inference-side alone introduces train/serve skew. The "fresh release wrongly
    # treated as a 5x suspect-peak" issue is a training-pipeline fix → retrain bundle.
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

    # --- Discovery Mode opt-in (latest manual S4A entry; default 0 = not opted in) ---
    dm_row = db.fetch_query(
        """SELECT opted_in FROM s4a_song_discovery_mode
           WHERE artist_id = %s AND song = %s
           ORDER BY recorded_at DESC LIMIT 1""",
        (artist_id, song),
    )
    discovery_mode = 1.0 if (dm_row and dm_row[0][0]) else 0.0
    # A 0 means BOTH "opted-out" and "never entered" — track which, so the UI can tell a
    # real opt-out from a missing-data 0 (Discovery Mode has no API source; ~35% unknown).
    discovery_mode_known = bool(dm_row)

    # --- Playlist adds (28-day snapshot) from manual S4A entries ---
    # Latest '28d' windowed snapshot (migration 044); not a sum, to match how S4A
    # reports the figure and how it is entered in the Saisie S4A grid.
    pa_row = db.fetch_query(
        """SELECT count FROM s4a_song_playlist_adds
           WHERE artist_id = %s AND song = %s AND time_window = '28d'
           ORDER BY recorded_at DESC LIMIT 1""",
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
        "IsThisSongOptedIntoSpotifyDiscoveryMode": discovery_mode,  # manual S4A entry (s4a_song_discovery_mode)
        "ReleaseConsistencyNum": float(release_consistency),
        "DaysSinceRelease": float(days_since),
        "NonAlgoStreams28Days_log": 0.0,                 # non disponible (split par source — Phase 2)
        "ListenersStreamRatio28Days_adj": float(ratio),
        "SavesLast28Days_adj": float(saves_28d),
        "PlaylistAddsLast28Days_adj": float(playlist_adds_28d),
        # Threshold 35 (not 30): mirrors the training label ReleasePhaseEarly
        # (TRUE iff released within the last 35 days — verified in data_anon.csv).
        "ReleasePhaseEarly": 1.0 if days_since < 35 else 0.0,
        "Velocity_Streams": float(velocity),
    }

    # Extra raw values pour features_json (non utilisés pour ML)
    features["_raw_streams_7d"] = s7
    features["_raw_streams_28d"] = s28
    features["_raw_followers"] = followers
    # Persisted (no underscore) so the dashboard distinguishes a real Discovery-Mode
    # opt-out from a missing-data 0. Ignored by the model (not in FEATURE_COLUMNS).
    features["discovery_mode_known"] = discovery_mode_known

    # Raw inputs for the PI regressor (order = PI_FEATURE_COLUMNS). 28-day window
    # globals mirror the training columns ListenersLast28Days / StreamsLast28Days /
    # SavesLast28Days / PlaylistAddsLast28Days.
    features["_pi_inputs"] = [
        float(listeners_global), float(streams_global), float(saves_28d),
        float(playlist_adds_28d), float(followers), float(days_since),
    ]

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
        dw_prob = _calibrate("dw", dw_clf.predict_proba(X)[0, 1])
    except Exception as e:
        logger.warning(f"DW classifier indisponible: {e}")
        dw_prob = None

    try:
        rr_clf = load_model("rr_classifier")
        rr_prob = _calibrate("rr", rr_clf.predict_proba(X)[0, 1])
    except Exception as e:
        logger.warning(f"RR classifier indisponible: {e}")
        rr_prob = None

    try:
        radio_clf = load_model("radio_classifier")
        radio_prob = _calibrate("radio", radio_clf.predict_proba(X)[0, 1])
    except Exception as e:
        logger.warning(f"Radio classifier indisponible: {e}")
        radio_prob = None

    # Log-target regressors (expm1). DW volume is suppressed: its honest group-CV R²
    # is negative (worse than the mean) — surfacing a number would mislead. RR/Radio
    # are floors only (R² 0.23/0.33). The display layer gates on ALGO_REGRESSOR_METRICS.
    dw_forecast = None
    rr_forecast = _volume_forecast("rr_regressor", X)
    radio_forecast = _volume_forecast("radio_regressor", X)

    # PI regressor uses its own raw-feature vector (different from FEATURE_COLUMNS).
    pi_inputs = features.get("_pi_inputs")
    try:
        if pi_inputs is None:
            raise ValueError("_pi_inputs absent des features")
        pi_reg = load_model("pi_regressor")
        X_pi = pd.DataFrame([pi_inputs], columns=PI_FEATURE_COLUMNS)
        pi_forecast = int(np.clip(pi_reg.predict(X_pi)[0], 0, 100))
    except Exception as e:
        logger.warning(f"PI regressor indisponible: {e}")
        pi_forecast = None

    return {
        "dw_probability": dw_prob,
        "rr_probability": rr_prob,
        "radio_probability": radio_prob,
        "dw_streams_forecast_7d": dw_forecast,
        "rr_streams_forecast_7d": rr_forecast,
        "radio_streams_forecast_7d": radio_forecast,
        "pi_forecast": pi_forecast,
    }


_ALGO_CLF_KEY = {"DW": "dw", "RR": "rr", "RADIO": "radio"}


def local_sensitivity(algo: str, feature: str, feats: dict, n_points: int = 25) -> dict | None:
    """Per-song local sensitivity: sweep ONE feature, recompute the calibrated probability.

    This is honest *local* partial dependence — "for THIS song, if you move this lever, the
    odds move like so" — NOT a global "+X = +Y%" rule (XGBoost is non-linear, so the curve is
    specific to this song's other features). Sweeps the lever in human units (expm1 for _log
    features), holding everything else fixed. Returns {x_human, probs, current} or None.
    """
    key = _ALGO_CLF_KEY.get(algo)
    if key is None or feature not in FEATURE_COLUMNS or not feats:
        return None
    base = [float(feats.get(c, 0.0)) for c in FEATURE_COLUMNS]
    idx = FEATURE_COLUMNS.index(feature)
    is_log = feature.endswith("_log")
    cur_human = float(np.expm1(base[idx])) if is_log else base[idx]
    stats = _load_json("metrics.json").get("feature_stats", {}).get(feature, {})
    # Upper bound = the bulk of the training distribution (mean+3σ), capped by the max, so
    # the curve has resolution in the meaningful range instead of a long flat tail.
    hi_model = stats.get("max", base[idx] * 2 or 1.0)
    if "mean" in stats and "std" in stats:
        hi_model = min(hi_model, stats["mean"] + 3.0 * stats["std"])
    hi_human = float(np.expm1(hi_model)) if is_log else float(hi_model)
    hi_human = max(hi_human, cur_human * 1.5, 1.0)
    try:
        clf = load_model(f"{key}_classifier")
    except Exception as e:
        logger.warning(f"local_sensitivity {algo}/{feature} indisponible: {e}")
        return None
    xs = np.linspace(0.0, hi_human, n_points)
    probs = []
    for xh in xs:
        vec = base.copy()
        vec[idx] = float(np.log1p(xh)) if is_log else float(xh)
        X = pd.DataFrame([vec], columns=FEATURE_COLUMNS)
        probs.append(_calibrate(key, float(clf.predict_proba(X)[0, 1])))
    return {"feature": feature, "x_human": xs.tolist(), "probs": probs, "current": cur_human}


def estimate_rr_prerelease(followers: float, days_since_release: float,
                           catalog_size: float, release_consistency_weeks: float,
                           discovery_mode: bool) -> dict | None:
    """Pre-release Release Radar probability from release-day metadata only (no streams).

    Serves models/v3/rr_premiere_classifier.ubj (AUC ~0.92 group-CV). A what-if planning
    tool: estimate RR odds BEFORE any stream exists, from artist size, catalogue depth,
    release cadence, song age and the Discovery-Mode choice. Returns the Platt-calibrated
    probability + the model's CV band, or None if the model/metadata is unavailable.
    """
    meta = _load_json("premiere.json")
    feats = {
        "CurrentSpotifyFollowers_log": float(np.log1p(max(0.0, followers))),
        "HowManySongsHasThisArtistEverReleased": float(max(0.0, catalog_size)),
        "IsThisSongOptedIntoSpotifyDiscoveryMode": 1.0 if discovery_mode else 0.0,
        "ReleaseConsistencyNum": float(max(0.0, release_consistency_weeks)),
        "DaysSinceRelease": float(max(0.0, days_since_release)),
        "ReleasePhaseEarly": 1.0 if days_since_release < 35 else 0.0,
    }
    X = pd.DataFrame([[feats[c] for c in PREMIERE_FEATURE_COLUMNS]],
                     columns=PREMIERE_FEATURE_COLUMNS)
    try:
        clf = load_model("rr_premiere_classifier")
        p_raw = float(clf.predict_proba(X)[0, 1])
    except Exception as e:
        logger.warning(f"RR premiere estimator indisponible: {e}")
        return None
    cal = meta.get("calibration")
    if cal:
        z = cal["coef"] * p_raw + cal["intercept"]
        p_raw = float(1.0 / (1.0 + np.exp(-z)))
    return {"rr_probability": p_raw, "cv": meta.get("cv", {})}


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

            drifted = check_drift(features)
            if drifted:
                logger.warning(f"  Drift {song!r}: features hors distribution {drifted}")

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
                "pi_forecast_7d": predictions.get("pi_forecast"),
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
