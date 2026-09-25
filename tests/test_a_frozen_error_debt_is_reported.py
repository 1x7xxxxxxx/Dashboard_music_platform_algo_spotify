"""A catalogue debt that stops falling is reported every night.

Type: Sub
Uses: tools/dev/error_debt_trend.py (frozen), .github/workflows/security-nightly.yml
Depends on: nothing — fabricated snapshots
"""
import importlib.util
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("edt", _ROOT / "tools/dev/error_debt_trend.py")
edt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(edt)


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """The six-commit freeze of 2026-09-25, a fall, and an older schema without the keys."""
    freeze = {"guard_does_not_prove_itself": 306, "cause_unknown": 140, "seen_red_unknown": 140}
    assert edt.frozen(freeze, dict(freeze)), "nothing fell: frozen"
    assert not edt.frozen(freeze, {**freeze, "guard_does_not_prove_itself": 300})
    assert edt.frozen(freeze, {**freeze, "cause_unknown": 141}), "a rise is not a fall"
    assert not edt.frozen({"other": 1}, freeze), "no common key: nothing can be concluded"


def test_the_nightly_runs_it_and_mails_it() -> None:
    wf = yaml.safe_load((_ROOT / ".github/workflows/security-nightly.yml").read_text(encoding="utf-8"))
    assert "error_debt_trend.py" in str(wf["jobs"]["debt-trend"]["steps"])
    assert "debt-trend" in wf["jobs"]["notify"]["needs"]
