"""`make error-debt` puts the classes that already RECURRED without a self-proving guard first.

Type: Sub
Uses: tools/dev/error_debt.py
Depends on: nothing — fabricated catalogue text and health rows

On 2026-09-25 the catalogue's debt had not moved in six commits (306 guards that do not
prove themselves, 140 unknown causes): ratchets forbid a rise, nothing proposed a fall.
"""
import importlib.util
from pathlib import Path

_TOOL = Path(__file__).resolve().parents[1] / "tools/dev/error_debt.py"
_spec = importlib.util.spec_from_file_location("error_debt", _TOOL)
debt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(debt)

_TEXT = """## came-back-twice
- History:
  - 2026-09-01 (récidive): a
  - 2026-09-02 (récidive): b
## came-back-but-proven
- History:
  - 2026-09-01 (récidive): a
## never-came-back
- History:
  - 2026-09-01: a note, not a recurrence
"""


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    recur = debt.recurrences(_TEXT)
    assert recur == {"came-back-twice": 2, "came-back-but-proven": 1, "never-came-back": 0}
    classes = {"came-back-twice": {"seen_red": "2026-09-01", "cause_evidence": "read"},
               "came-back-but-proven": {"seen_red": "self-proving", "cause_evidence": "read"},
               "never-came-back": {"seen_red": "unknown", "cause_evidence": "unknown"}}
    ids = [cid for cid, _ in debt.work_list(classes, recur, 10)]
    assert ids == ["came-back-twice", "never-came-back"], ids


def test_the_ceilings_are_read_from_the_ratchet() -> None:
    assert "guard_does_not_prove_itself" in debt.ceilings()
