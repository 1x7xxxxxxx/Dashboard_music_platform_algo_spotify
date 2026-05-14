"""Non-regression tests for src/utils/ml_inference.py.

Why this file exists : 5 XGBoost models live as hard-coded paths in
MODEL_PATHS (src/utils/ml_inference.py:30-36). A typo in a path, a swap of
a UBJ artifact, or a reorder of FEATURE_COLUMNS would silently change
predictions. These tests catch that at PR time.

Three tiers of assertion :
- Structural (always run) : signature, dict keys, FEATURE_COLUMNS length, MODEL_VERSION type.
- Value-range (skipped if xgboost missing) : probabilities ∈ [0, 1], forecasts ≥ 0, no NaN.
- Baseline freeze (skipped if baseline file missing) : output within ±5 % of frozen reference.

Regenerating the baseline : run `python3 tests/fixtures/generate_ml_baseline.py`
in an environment with xgboost installed and the models reachable.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from src.utils.ml_inference import (
    FEATURE_COLUMNS,
    MODEL_PATHS,
    MODEL_VERSION,
    score_song,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
INPUT_FILE = FIXTURE_DIR / "ml_scoring_input.json"
BASELINE_FILE = FIXTURE_DIR / "ml_scoring_baseline.json"
EXPECTED_KEYS = {
    "dw_probability",
    "rr_probability",
    "radio_probability",
    "dw_streams_forecast_7d",
    "rr_streams_forecast_7d",
}
PROBABILITY_KEYS = {"dw_probability", "rr_probability", "radio_probability"}
FORECAST_KEYS = {"dw_streams_forecast_7d", "rr_streams_forecast_7d"}
BASELINE_TOLERANCE = 0.05  # ±5 % drift threshold


@pytest.fixture(scope="module")
def fixtures() -> list[dict]:
    return json.loads(INPUT_FILE.read_text())


def _features(fx: dict) -> dict:
    return {k: v for k, v in fx.items() if not k.startswith("_")}


def _models_loadable() -> bool:
    try:
        import xgboost  # noqa: F401
    except ImportError:
        return False
    from src.utils.ml_inference import _resolve_path
    return all(Path(_resolve_path(p)).exists() for p in MODEL_PATHS.values())


# ─────────────────────────────────────────────────────────────────────
# Tier 1 — Structural (always run, even without xgboost installed)
# ─────────────────────────────────────────────────────────────────────

class TestStructure:
    def test_feature_columns_count_is_13(self):
        # Frozen contract: changing the count requires updating both fixtures
        # and the baseline. The number itself is in the model artifact signature.
        assert len(FEATURE_COLUMNS) == 13

    def test_feature_columns_are_unique(self):
        assert len(set(FEATURE_COLUMNS)) == len(FEATURE_COLUMNS)

    def test_model_paths_has_five_models(self):
        assert set(MODEL_PATHS) == {
            "dw_classifier", "radio_classifier", "rr_classifier",
            "dw_regressor", "rr_regressor",
        }

    def test_model_version_is_non_empty_string(self):
        assert isinstance(MODEL_VERSION, str) and MODEL_VERSION

    def test_score_song_returns_expected_keys(self, fixtures):
        # Works even when xgboost is missing — score_song catches the
        # ImportError and returns None for each key, but the keys are present.
        out = score_song(_features(fixtures[0]))
        assert set(out) == EXPECTED_KEYS


# ─────────────────────────────────────────────────────────────────────
# Tier 2 — Value range (requires xgboost + models reachable)
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _models_loadable(),
                    reason="xgboost unavailable or model artifacts missing")
class TestValueRanges:
    def test_probabilities_in_unit_interval(self, fixtures):
        for fx in fixtures:
            out = score_song(_features(fx))
            for key in PROBABILITY_KEYS:
                p = out[key]
                assert p is not None, f"{fx['_label']}: {key} is None"
                assert 0.0 <= p <= 1.0, f"{fx['_label']}: {key}={p} out of [0,1]"

    def test_forecasts_are_non_negative_finite_ints(self, fixtures):
        for fx in fixtures:
            out = score_song(_features(fx))
            for key in FORECAST_KEYS:
                f = out[key]
                assert f is not None, f"{fx['_label']}: {key} is None"
                assert isinstance(f, int), f"{fx['_label']}: {key} is {type(f).__name__}, not int"
                assert f >= 0, f"{fx['_label']}: {key}={f} negative"
                assert math.isfinite(f)

    def test_no_nan_anywhere(self, fixtures):
        for fx in fixtures:
            out = score_song(_features(fx))
            for key, value in out.items():
                assert value is not None, f"{fx['_label']}: {key} None"
                assert math.isfinite(value), f"{fx['_label']}: {key}={value} not finite"


# ─────────────────────────────────────────────────────────────────────
# Tier 3 — Baseline regression (frozen reference, requires baseline file)
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not BASELINE_FILE.exists(),
                    reason="baseline missing — run tests/fixtures/generate_ml_baseline.py")
@pytest.mark.skipif(not _models_loadable(),
                    reason="xgboost unavailable or model artifacts missing")
class TestBaselineRegression:
    def test_model_version_matches_baseline(self):
        baseline = json.loads(BASELINE_FILE.read_text())
        assert baseline["model_version"] == MODEL_VERSION, (
            f"MODEL_VERSION bumped to {MODEL_VERSION!r} but baseline still on "
            f"{baseline['model_version']!r}. Regenerate baseline."
        )

    def test_predictions_within_tolerance_of_baseline(self, fixtures):
        baseline = json.loads(BASELINE_FILE.read_text())
        baseline_by_label = {row["_label"]: row for row in baseline["rows"]}

        for fx in fixtures:
            label = fx["_label"]
            assert label in baseline_by_label, f"baseline missing row for {label!r}"
            out = score_song(_features(fx))
            expected = baseline_by_label[label]
            for key in EXPECTED_KEYS:
                actual = out[key]
                ref = expected[key]
                # Allow exact match when ref is 0 (avoid div by zero)
                if ref == 0:
                    assert actual == 0, f"{label}/{key}: baseline=0 but got {actual}"
                    continue
                rel_diff = abs(actual - ref) / abs(ref)
                assert rel_diff <= BASELINE_TOLERANCE, (
                    f"{label}/{key}: {actual} vs baseline {ref} "
                    f"(rel_diff={rel_diff:.3f} > {BASELINE_TOLERANCE})"
                )
