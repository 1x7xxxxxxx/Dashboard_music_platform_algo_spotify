"""Tests for the ML outcome-labelling engine (migration 060)."""
from datetime import date

import pandas as pd
import pytest

from src.utils.ml_outcome_labeling import (
    TARGET_THRESHOLDS,
    bin_label,
    label_predictions,
    match_outcome,
)


class TestBinLabel:
    def test_thresholds_match_training(self):
        # Source of truth: machine_learning/train.py:45
        assert TARGET_THRESHOLDS == {"dw": 137, "rr": 130, "radio": 639}

    def test_strictly_greater(self):
        # train.py uses (streams > threshold), so the threshold value itself is a 0.
        assert bin_label(137, "dw") == 0
        assert bin_label(138, "dw") == 1
        assert bin_label(130, "rr") == 0
        assert bin_label(131, "rr") == 1
        assert bin_label(639, "radio") == 0
        assert bin_label(640, "radio") == 1

    def test_none_and_garbage_default_zero(self):
        assert bin_label(None, "dw") == 0
        assert bin_label("not-a-number", "dw") == 0

    def test_unknown_target_raises(self):
        with pytest.raises(ValueError):
            bin_label(100, "nope")


class TestMatchOutcome:
    @staticmethod
    def _obs(d, dw=0, rr=0, radio=0):
        return {"recorded_at": d, "dw_streams_28d": dw,
                "rr_streams_28d": rr, "radio_streams_28d": radio}

    def test_picks_earliest_past_horizon(self):
        pred = date(2026, 1, 1)  # cutoff = 2026-01-29
        obs = [self._obs(date(2026, 1, 20)),          # too early
               self._obs(date(2026, 2, 10)),          # eligible but later
               self._obs(date(2026, 1, 29), dw=500)]  # earliest eligible
        chosen = match_outcome(pred, obs, 28)
        assert chosen["recorded_at"] == date(2026, 1, 29)
        assert chosen["dw_streams_28d"] == 500

    def test_none_when_nothing_late_enough(self):
        assert match_outcome(date(2026, 1, 1), [self._obs(date(2026, 1, 15))], 28) is None

    def test_empty(self):
        assert match_outcome(date(2026, 1, 1), [], 28) is None


class _FakeDB:
    """Routes fetch_df by query text; captures the upsert."""

    def __init__(self, preds_df, outcomes_df):
        self._preds = preds_df
        self._outcomes = outcomes_df
        self.upserts = []

    def fetch_df(self, sql, params=None):
        return self._preds if "ml_song_predictions" in sql else self._outcomes

    def upsert_many(self, table, data, conflict_columns, update_columns):
        self.upserts.append((table, data, conflict_columns, update_columns))
        return len(data)


class TestLabelPredictions:
    def test_labels_only_matched_predictions(self):
        preds = pd.DataFrame([
            {"id": 1, "song": "A", "prediction_date": date(2026, 1, 1), "model_version": "v3"},
            {"id": 2, "song": "B", "prediction_date": date(2026, 1, 1), "model_version": "v3"},
        ])
        outcomes = pd.DataFrame([  # only A has a realized outcome past the horizon
            {"song": "A", "recorded_at": date(2026, 1, 29),
             "dw_streams_28d": 500, "rr_streams_28d": 50, "radio_streams_28d": 700},
        ])
        db = _FakeDB(preds, outcomes)
        n = label_predictions(db, artist_id=1)

        assert n == 1
        table, data, conflict, _ = db.upserts[0]
        assert table == "ml_prediction_outcomes"
        assert conflict == ["prediction_id"]
        row = data[0]
        assert row["prediction_id"] == 1
        assert (row["y_dw"], row["y_rr"], row["y_radio"]) == (1, 0, 1)  # 500>137, 50<=130, 700>639
        assert row["horizon_days"] == 28
        assert row["observed_at"] == date(2026, 1, 29)

    def test_no_predictions_returns_zero(self):
        assert label_predictions(_FakeDB(pd.DataFrame(), pd.DataFrame()), artist_id=1) == 0

    def test_no_outcomes_returns_zero(self):
        preds = pd.DataFrame([
            {"id": 1, "song": "A", "prediction_date": date(2026, 1, 1), "model_version": "v3"},
        ])
        db = _FakeDB(preds, pd.DataFrame())
        assert label_predictions(db, artist_id=1) == 0
        assert db.upserts == []
