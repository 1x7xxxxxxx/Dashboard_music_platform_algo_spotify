"""The action-drift report prints the two marks its catalogue signatures grep for.

Type: Sub
Uses: tools/dev/check_action_drift.py (row_marks)
Depends on: nothing — no GitHub call

Classes `a-prudence-rule-with-no-expiry-becomes-a-freeze` (a pin two majors behind → 🔴)
and `an-action-pin-derived-from-a-version-number` (a tag that does not exist upstream →
INTROUVABLE). Their signatures grep the report; nothing proved the report could print them.
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_action_drift", Path(__file__).resolve().parents[1] / "tools/dev/check_action_drift.py")
cad = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cad)


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """setup-uv held six majors behind (the freeze) → 🔴 ; `@v10`, a tag deduced from a
    version number and absent upstream → INTROUVABLE ; an unanswered API → ❓, not a verdict."""
    assert cad.row_marks(6, True)[0] == "🔴"
    assert cad.row_marks(1, True)[0] == "🟠"
    assert cad.row_marks(0, True) == ("✅", "✅")
    assert "INTROUVABLE" in cad.row_marks(0, False)[1]
    assert "INTROUVABLE" not in cad.row_marks(0, None)[1], "could not ask is not absent"
