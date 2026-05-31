"""
Type: Utility
Reproducible training pipeline for the Spotify algorithm models.

Replaces the 104 MB exploratory notebook (data_analysis_ml_perso.ipynb) as the
canonical, runnable training entrypoint. Trains, scaler-free, the models served
by src/utils/ml_inference.py:

- 3 classifiers   : Discover Weekly / Release Radar / Radio trigger probability
- 3 volume regressors : 7-day stream forecast per algorithm
- 1 PI regressor  : Popularity Index (0-100) forecast

Why scaler-free: the deployed v1 models were trained WITH StandardScaler but
inference applied none, so the served thresholds were in z-score space while raw
values were passed -> structurally wrong probabilities. XGBoost is invariant to
monotonic per-feature scaling, so dropping the scaler is loss-free AND removes the
train/serve skew. This module trains exactly the 13-feature inference contract.

Uses: machine_learning/01_data/data_anon.csv (gitignored, local only)
Persists in: machine_learning/models/<MODEL_VERSION>/*.ubj  + threshold_tables.json
Triggers: manual run `python3 machine_learning/train.py`
Depends on: xgboost, scikit-learn, imbalanced-learn (SMOTE)
"""
import json
import os

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.metrics import mean_absolute_error, r2_score, roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier, XGBRegressor

MODEL_VERSION = "v2_noscaler"

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.environ.get("ML_TRAIN_DATA", os.path.join(_HERE, "01_data", "data_anon.csv"))
OUT_DIR = os.path.join(_HERE, "models", MODEL_VERSION)

RANDOM_STATE = 42
TEST_SIZE = 0.2

# Classification target thresholds (28-day algo streams) — from the notebook.
TARGET_THRESHOLDS = {"dw": 137, "rr": 130, "radio": 639}

# Exact feature contract served by src/utils/ml_inference.py:FEATURE_COLUMNS.
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

# PI regressor features (notebook "SCRIPT MASTER" — raw, no log).
PI_FEATURES = [
    "ListenersLast28Days", "StreamsLast28Days", "SavesLast28Days",
    "PlaylistAddsLast28Days", "CurrentSpotifyFollowers", "DaysSinceRelease",
]

_BOOL_MAP = {"Yes": 1, "No": 0, "yes": 1, "no": 0, "TRUE": 1, "FALSE": 0,
             "True": 1, "False": 0, True: 1, False: 0}


def _velocity(s7: pd.Series, s28: pd.Series) -> pd.Series:
    """Mirror src/utils/ml_inference.py exactly: no-prior+streams -> 5.0, else 1.0."""
    avg_7d = s7 / 7.0
    prior_21d = (s28 - s7).clip(lower=0)
    avg_prior = prior_21d / 21.0
    vel = np.where(avg_prior > 0, avg_7d / avg_prior.replace(0, np.nan),
                   np.where(avg_7d > 0, 5.0, 1.0))
    return pd.Series(np.clip(np.nan_to_num(vel, nan=1.0), 0.0, 5.0), index=s7.index)


def build_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Build the 13 inference features + classification targets from raw columns."""
    num_cols = df.select_dtypes(include=[np.number]).columns
    df[num_cols] = df[num_cols].clip(lower=0)
    for col in num_cols:
        if df[col].isnull().any():
            df[col] = df[col].fillna(df[col].median())

    out = pd.DataFrame(index=df.index)
    out["StreamsLast7Days_log"] = np.log1p(df["StreamsLast7Days"].fillna(0))
    out["CurrentSpotifyFollowers_log"] = np.log1p(df["CurrentSpotifyFollowers"].fillna(0))
    out["HowManySongsDoYouHaveInRadioRightNow"] = df["HowManySongsDoYouHaveInRadioRightNow"].fillna(0)
    out["HowManySongsHasThisArtistEverReleased"] = df["HowManySongsHasThisArtistEverReleased"].fillna(0)
    out["IsThisSongOptedIntoSpotifyDiscoveryMode"] = (
        df["IsThisSongOptedIntoSpotifyDiscoveryMode"].map(_BOOL_MAP).fillna(0).astype(int)
    )
    out["ReleaseConsistencyNum"] = df["ReleaseConsistencyNum"].fillna(df["ReleaseConsistencyNum"].median())
    out["DaysSinceRelease"] = df["DaysSinceRelease"].fillna(0)
    out["NonAlgoStreams28Days_log"] = np.log1p(df["NonAlgoStreams28Days"].fillna(0))
    # IMPORTANT: the CSV's *_adj columns are an UNRECOVERABLE upstream adjustment
    # (residuals, negative values) that inference cannot reproduce from live DB
    # data. To kill train/serve skew we train on exactly what build_features()
    # computes: raw streams/listeners ratio + raw Saves/PlaylistAdds counts.
    # Feature NAMES keep the *_adj suffix (the model's column contract) but the
    # VALUES now match inference. See src/utils/ml_inference.py build_features().
    listeners28 = df["ListenersLast28Days"].fillna(0)
    out["ListenersStreamRatio28Days_adj"] = np.where(
        listeners28 > 0, df["StreamsLast28Days"].fillna(0) / listeners28, 0.0
    )
    out["SavesLast28Days_adj"] = df["SavesLast28Days"].fillna(0)
    out["PlaylistAddsLast28Days_adj"] = df["PlaylistAddsLast28Days"].fillna(0)
    out["ReleasePhaseEarly"] = df["ReleasePhaseEarly"].map(_BOOL_MAP).fillna(0).astype(int)
    out["Velocity_Streams"] = _velocity(df["StreamsLast7Days"].fillna(0), df["StreamsLast28Days"].fillna(0))

    out = out[FEATURE_COLUMNS].astype(float)
    out["y_dw"] = (df["DiscoverWeeklyStreamsLast28Days"].fillna(0) > TARGET_THRESHOLDS["dw"]).astype(int)
    out["y_rr"] = (df["ReleaseRadarStreamsLast28Days"].fillna(0) > TARGET_THRESHOLDS["rr"]).astype(int)
    out["y_radio"] = (df["RadioStreamsLast28Days"].fillna(0) > TARGET_THRESHOLDS["radio"]).astype(int)
    # Regressor targets: 28-day algo stream volume. NOTE: the deployed inference
    # stores these under *_streams_forecast_7d, but the notebook/deployed model
    # regresses the 28-DAY column — a pre-existing naming mismatch kept as-is to
    # preserve the schema/view contract (flagged to the user separately).
    out["v_dw"] = df["DiscoverWeeklyStreamsLast28Days"].fillna(0)
    out["v_rr"] = df["ReleaseRadarStreamsLast28Days"].fillna(0)
    out["v_radio"] = df["RadioStreamsLast28Days"].fillna(0)
    return out


def _clf() -> XGBClassifier:
    return XGBClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.9, colsample_bytree=0.9, eval_metric="logloss",
        random_state=RANDOM_STATE,
    )


def _reg() -> XGBRegressor:
    return XGBRegressor(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.9, colsample_bytree=0.9, random_state=RANDOM_STATE,
    )


def train_classifiers(ds: pd.DataFrame) -> dict:
    X = ds[FEATURE_COLUMNS]
    results = {}
    for algo, use_smote in (("dw", True), ("rr", True), ("radio", False)):
        y = ds[f"y_{algo}"]
        Xtr, Xte, ytr, yte = train_test_split(
            X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
        )
        if use_smote and ytr.sum() >= 6:
            Xtr, ytr = SMOTE(random_state=RANDOM_STATE).fit_resample(Xtr, ytr)
        clf = _clf().fit(Xtr, ytr)
        auc = roc_auc_score(yte, clf.predict_proba(Xte)[:, 1]) if yte.nunique() > 1 else float("nan")
        clf.save_model(os.path.join(OUT_DIR, f"{algo}_classifier.ubj"))
        results[algo] = {"auc": round(float(auc), 3), "n_test": int(len(yte)), "positives": int(y.sum())}
        print(f"  [clf] {algo:5s} AUC={auc:.3f}  test_n={len(yte)}  positives={int(y.sum())}/{len(y)}")
    return results


def train_regressors(ds: pd.DataFrame) -> dict:
    X = ds[FEATURE_COLUMNS]
    results = {}
    for algo in ("dw", "rr", "radio"):
        y = ds[f"v_{algo}"]
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE)
        reg = _reg().fit(Xtr, ytr)
        r2 = r2_score(yte, reg.predict(Xte))
        reg.save_model(os.path.join(OUT_DIR, f"{algo}_regressor.ubj"))
        results[algo] = {"r2": round(float(r2), 3)}
        flag = "" if r2 >= 0.5 else "  (UNRELIABLE — classification-only)"
        print(f"  [reg] {algo:5s} R²={r2:.3f}{flag}")
    return results


def train_pi(df: pd.DataFrame) -> dict:
    sub = df.dropna(subset=["PopularityIndex", *PI_FEATURES]).copy()
    X, y = sub[PI_FEATURES], sub["PopularityIndex"]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE)
    pi = XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=RANDOM_STATE)
    pi.fit(Xtr, ytr)
    pred = np.clip(pi.predict(Xte), 0, 100)
    r2, mae = r2_score(yte, pred), mean_absolute_error(yte, pred)
    pi.save_model(os.path.join(OUT_DIR, "pi_regressor.ubj"))
    print(f"  [pi]  R²={r2:.3f}  MAE={mae:.1f} PI points")
    return {"r2": round(float(r2), 3), "mae": round(float(mae), 2), "features": PI_FEATURES}


def export_threshold_tables(df: pd.DataFrame) -> dict:
    """Per-PI-bracket trigger probabilities (the bar-chart data) for the B2 view."""
    d = df.dropna(subset=["PopularityIndex"]).copy()
    bins = [0, 10, 20, 30, 40, 50, 100]
    labels = ["0-10", "11-20", "21-30", "31-40", "41-50", "50+"]
    d["PI_Group"] = pd.cut(d["PopularityIndex"], bins=bins, labels=labels, include_lowest=True)
    d["trig_rr"] = (d["ReleaseRadarStreamsLast7Days"].fillna(0) > 0).astype(int)
    d["trig_dw"] = (d["DiscoverWeeklyStreamsLast7Days"].fillna(0) > 0).astype(int)
    d["trig_radio"] = (d["RadioStreamsLast7Days"].fillna(0) > 0).astype(int)
    d_rr = d[d["DaysSinceRelease"] <= 35]

    def _by_group(frame, col):
        means = frame.groupby("PI_Group", observed=False)[col].mean()
        counts = frame.groupby("PI_Group", observed=False)[col].count()
        out = {}
        for k in means.index:
            n = int(counts[k])
            # n==0 -> prob null (empty bracket); never emit NaN (invalid JSON).
            prob = round(float(means[k]) * 100, 1) if n > 0 else None
            out[str(k)] = {"prob": prob, "n": n}
        return out

    return {
        "pi_brackets": labels,
        "release_radar": _by_group(d_rr, "trig_rr"),
        "discover_weekly": _by_group(d, "trig_dw"),
        "radio": _by_group(d, "trig_radio"),
        "note": "release_radar restricted to songs <=35 days; n = sample count per bracket",
    }


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"=== Training {MODEL_VERSION} from {DATA_PATH} ===")
    df = pd.read_csv(DATA_PATH)
    print(f"rows={len(df)}  cols={df.shape[1]}\n")

    ds = build_dataset(df.copy())
    print("Classifiers (scaler-free):")
    clf_metrics = train_classifiers(ds)
    print("Volume regressors:")
    reg_metrics = train_regressors(ds)
    print("Popularity Index regressor:")
    pi_metrics = train_pi(df.copy())
    print("Exporting PI threshold tables...")
    thresholds = export_threshold_tables(df.copy())

    metrics = {
        "model_version": MODEL_VERSION, "rows": int(len(df)),
        "features": FEATURE_COLUMNS, "classifiers": clf_metrics,
        "regressors": reg_metrics, "pi": pi_metrics,
    }
    with open(os.path.join(OUT_DIR, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    with open(os.path.join(OUT_DIR, "threshold_tables.json"), "w") as f:
        json.dump(thresholds, f, indent=2)
    print(f"\n✅ Saved 7 models + metrics.json + threshold_tables.json -> {OUT_DIR}")


if __name__ == "__main__":
    main()
