"""A dependency pinned in two manifests carries the same version in both.

Type: Sub
Uses: tools/dev/check_manifest_consistency.py (_drift)
Depends on: nothing — fabricated manifests

Class `streamlit-pin-drift`: `pyproject.toml`, `requirements.txt` and `uv.lock` pinned
three different Streamlits; the image installed one, the lock another.
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "cmc", Path(__file__).resolve().parents[1] / "tools/dev/check_manifest_consistency.py")
cmc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cmc)


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Two sources disagreeing is drift; agreeing is not; a name present in ONE source only
    has nothing to disagree with."""
    drift = cmc._drift({"pyproject": {"streamlit": "1.54.0"},
                        "requirements": {"streamlit": "1.50.0"},
                        "uv.lock": {"streamlit": "1.54.0", "only-here": "2.0"}})
    assert len(drift) == 1 and "streamlit" in drift[0], drift
    assert cmc._drift({"a": {"x": "1"}, "b": {"x": "1"}}) == []
    assert len(cmc._drift({"pyproject": {"x": "1"}, "requirements": {"x": "2"}})) == 1, \
        "TWO sources disagreeing is already drift — the image and the lock differ"
