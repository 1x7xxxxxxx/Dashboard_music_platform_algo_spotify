"""R355 — `machine_learning/train.py` loads without imbalanced-learn.

Type: Sub
Uses: machine_learning/train.py
Depends on: xgboost, scikit-learn (skipped when absent)

The export scripts (`export_algo_stream_estimates.py`, `derive_thresholds.py`, …) import
train.py for its constants only. A top-level `from imblearn …` made every one of them crash
in the project venv, which has no imbalanced-learn (defect log, 2026-09-27). The module is
loaded with `imblearn` BLOCKED, so the test holds whether or not the package is installed.
"""
import subprocess
import sys
from pathlib import Path

import pytest

ML = Path(__file__).resolve().parents[1] / "machine_learning"


def test_train_constants_load_with_imblearn_blocked():
    pytest.importorskip("xgboost")
    pytest.importorskip("sklearn")
    code = ("import sys; sys.modules['imblearn'] = None; "
            "sys.modules['imblearn.over_sampling'] = None; "
            "import train; assert train.TARGET_THRESHOLDS")
    r = subprocess.run([sys.executable, "-c", code], cwd=ML,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-800:]
