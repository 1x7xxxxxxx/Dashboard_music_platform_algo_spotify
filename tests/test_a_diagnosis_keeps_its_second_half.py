"""A diagnosis reaches its reader whole: never `.splitlines()[0]`, never raw into HTML.

Type: Sub
Uses: .claude/scripts/check_diagnosis_rendering.py (hits_in)
Depends on: nothing — fabricated consumers

Class `message-flattened-for-the-narrowest-renderer`: a diagnosis has two halves, what is
wrong and what to DO; the narrowest renderer kept the first line and dropped the second.
"""
import ast
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "cdr", Path(__file__).resolve().parents[1] / ".claude/scripts/check_diagnosis_rendering.py")
cdr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cdr)


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Both forms, fabricated, and their corrections."""
    flattened = ast.parse("short = probe['reason'].splitlines()[0]\n")
    raw_html = ast.parse("cell = f\"<td>{probe['next_action']}</td>\"\n")
    fixed = ast.parse("short = probe['reason']\ncell = f\"<td>{as_html(probe['next_action'])}</td>\"\n")
    assert len(cdr.hits_in(flattened, "x.py")) == 1
    assert len(cdr.hits_in(raw_html, "x.py")) == 1
    assert cdr.hits_in(fixed, "x.py") == []
