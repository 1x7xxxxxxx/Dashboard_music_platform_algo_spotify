#!/usr/bin/env python3
"""Regenerate tests/fixtures/ml_scoring_baseline.json from the current models.

Run this in an environment where xgboost is installed and the models in
machine_learning/models/<MODEL_VERSION>/ are loadable. The output file is
committed and used by tests/test_ml_inference.py to detect silent model swaps.

When to re-run :
- After deliberately updating a model artifact in MODEL_PATHS.
- After bumping MODEL_VERSION.
- After changing FEATURE_COLUMNS (the input fixture also needs updating).

Usage from repo root :
    python3 tests/fixtures/generate_ml_baseline.py

Then commit the regenerated baseline alongside the artifact change.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.utils.ml_inference import FEATURE_COLUMNS, MODEL_VERSION, score_song

FIXTURE_DIR = Path(__file__).parent
INPUT_FILE = FIXTURE_DIR / "ml_scoring_input.json"
BASELINE_FILE = FIXTURE_DIR / "ml_scoring_baseline.json"


def main() -> None:
    fixtures = json.loads(INPUT_FILE.read_text())
    baseline = {"model_version": MODEL_VERSION, "rows": []}

    for fx in fixtures:
        label = fx["_label"]
        # Keep _pi_inputs (consumed by the PI regressor); drop only _label so the
        # vector matches what build_features() hands to score_song in production.
        features = {k: v for k, v in fx.items() if k != "_label"}
        missing = [c for c in FEATURE_COLUMNS if c not in features]
        if missing:
            raise SystemExit(f"fixture {label!r} missing features: {missing}")
        out = score_song(features)
        # dw_streams_forecast_7d is intentionally None in v3 (DW volume suppressed,
        # R²<0). Any OTHER None means the models failed to load.
        _suppressed = {"dw_streams_forecast_7d"}
        if any(v is None for k, v in out.items() if k not in _suppressed):
            raise SystemExit(
                f"fixture {label!r} produced None — models not loaded. "
                "Make sure xgboost is installed and machine_learning/models/ "
                "is reachable."
            )
        baseline["rows"].append({"_label": label, **out})

    BASELINE_FILE.write_text(json.dumps(baseline, indent=2) + "\n")
    print(f"Wrote {BASELINE_FILE} ({len(baseline['rows'])} rows, MODEL_VERSION={MODEL_VERSION})")


if __name__ == "__main__":
    main()
