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



def test_a_manual_class_is_exempt_only_with_its_evidence() -> None:
    """2026-09-26: a recurred class that cannot have a detector leaves the self-proving list
    only when it declares manual + n-a + a sweep + an uncovered scope; one missing fact and
    it stays. Its unknown cause still ranks."""
    full = {"kind": "manual", "seen_red": "n-a", "siblings_swept": True,
            "guard_scope_has_not_covered": True, "cause_evidence": "read"}
    recur = {"m": 2}
    assert debt.work_list({"m": full}, recur, 10) == []
    for key in ("kind", "seen_red", "siblings_swept", "guard_scope_has_not_covered"):
        partial = {**full, key: {"kind": "heuristic", "seen_red": "never"}.get(key, False)}
        assert [c for c, _ in debt.work_list({"m": partial}, recur, 10)] == ["m"], key
    assert [c for c, _ in debt.work_list({"m": {**full, "cause_evidence": "unknown"}},
                                         recur, 10)] == ["m"]
