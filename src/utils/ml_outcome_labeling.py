"""Outcome-labelling engine — join ML predictions to realized DW/RR/Radio outcomes.

Type: Utility
Uses: PostgresHandler (fetch_df / upsert_many)
Triggers: called by the ml_outcome_labeling DAG (weekly)
Persists in: ml_prediction_outcomes
Depends on: ml_song_predictions (predictions), s4a_song_algo_outcomes (manual realized streams)

The scoring DAG logs P(DW/RR/Radio) per song per day into ml_song_predictions but the
model is never told whether it was right. This module pairs each prediction with the
realized 28-day DW/RR/Radio streams observed at least `min_horizon_days` later (manually
captured in s4a_song_algo_outcomes — S4A exposes no source split, ADR-004), bins them to
0/1 with the SAME thresholds used at training, and writes training-ready labelled rows.

Pure helpers (bin_label, match_outcome) carry the logic and are unit-tested; the thin
orchestrator label_predictions does the SQL. Thresholds mirror machine_learning/train.py:45
(kept local so the Airflow runtime needs no machine_learning/ import).
"""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

# Classification target thresholds (28-day algo streams). Source of truth:
# machine_learning/train.py:45 (TARGET_THRESHOLDS). A song is a positive label for an
# algorithm when its realized 28-day streams STRICTLY exceed the threshold (> not >=),
# matching train.py's `(streams > threshold).astype(int)`.
TARGET_THRESHOLDS = {"dw": 137, "rr": 130, "radio": 639}

_DEFAULT_HORIZON_DAYS = 28


def bin_label(streams, target: str) -> int:
    """1 if realized 28d streams exceed the training threshold for `target`, else 0."""
    if target not in TARGET_THRESHOLDS:
        raise ValueError(f"Unknown target {target!r}; expected one of {sorted(TARGET_THRESHOLDS)}")
    try:
        value = float(streams) if streams is not None else 0.0
    except (TypeError, ValueError):
        value = 0.0
    return int(value > TARGET_THRESHOLDS[target])


def match_outcome(prediction_date: date, observations: list, min_horizon_days: int = _DEFAULT_HORIZON_DAYS) -> Optional[dict]:
    """Pick the realized-outcome snapshot that labels a prediction.

    `observations` is a list of dicts with at least 'recorded_at' (date). The chosen
    snapshot is the EARLIEST one recorded at least `min_horizon_days` after the
    prediction — i.e. the first 28-day window fully observed past the horizon. Returns
    None when no snapshot is late enough yet (the prediction stays unlabelled).
    """
    cutoff = prediction_date + timedelta(days=min_horizon_days)
    eligible = [o for o in observations if o.get("recorded_at") and o["recorded_at"] >= cutoff]
    if not eligible:
        return None
    return min(eligible, key=lambda o: o["recorded_at"])


def _outcomes_by_song(db, artist_id: int) -> dict:
    """{song: [snapshot dicts sorted by recorded_at]} of realized 28d algo streams.

    Only the 28-day window feeds labels — that is the model's target horizon. The
    7d/custom rows captured for tracking are deliberately excluded here.
    """
    df = db.fetch_df(
        """SELECT song, recorded_at, dw_streams, rr_streams, radio_streams
           FROM s4a_song_algo_outcomes
           WHERE artist_id = %s AND time_window = '28d'
           ORDER BY song, recorded_at""",
        (artist_id,),
    )
    by_song: dict = {}
    if df is None or df.empty:
        return by_song
    for rec in df.to_dict("records"):
        by_song.setdefault(rec["song"], []).append(rec)
    return by_song


def label_predictions(db, artist_id: int, min_horizon_days: int = _DEFAULT_HORIZON_DAYS) -> int:
    """Label every still-unlabelled, old-enough prediction that has a realized outcome.

    Idempotent: predictions already in ml_prediction_outcomes are skipped (LEFT JOIN),
    and the upsert keys on prediction_id. Returns the number of new labels written.
    """
    preds = db.fetch_df(
        """SELECT p.id, p.song, p.prediction_date, p.model_version
           FROM ml_song_predictions p
           LEFT JOIN ml_prediction_outcomes o ON o.prediction_id = p.id
           WHERE p.artist_id = %s
             AND o.id IS NULL
             AND p.prediction_date <= CURRENT_DATE - %s
             AND p.song NOT ILIKE %s
           ORDER BY p.prediction_date""",
        (artist_id, min_horizon_days, "%1x7xxxxxxx%"),
    )
    if preds is None or preds.empty:
        return 0

    by_song = _outcomes_by_song(db, artist_id)
    if not by_song:
        return 0

    now = datetime.now(timezone.utc)
    rows = []
    for p in preds.to_dict("records"):
        obs = match_outcome(p["prediction_date"], by_song.get(p["song"], []), min_horizon_days)
        if obs is None:
            continue
        dw, rr, radio = obs["dw_streams"], obs["rr_streams"], obs["radio_streams"]
        rows.append({
            "prediction_id": int(p["id"]),
            "artist_id": artist_id,
            "song": p["song"],
            "prediction_date": p["prediction_date"],
            "observed_at": obs["recorded_at"],
            "horizon_days": (obs["recorded_at"] - p["prediction_date"]).days,
            "dw_streams_28d": int(dw or 0),
            "rr_streams_28d": int(rr or 0),
            "radio_streams_28d": int(radio or 0),
            "y_dw": bin_label(dw, "dw"),
            "y_rr": bin_label(rr, "rr"),
            "y_radio": bin_label(radio, "radio"),
            "model_version": p["model_version"],
            "labeled_at": now,
        })

    if not rows:
        return 0

    db.upsert_many(
        "ml_prediction_outcomes",
        rows,
        conflict_columns=["prediction_id"],
        update_columns=[
            "observed_at", "horizon_days", "dw_streams_28d", "rr_streams_28d",
            "radio_streams_28d", "y_dw", "y_rr", "y_radio", "model_version", "labeled_at",
        ],
    )
    return len(rows)
