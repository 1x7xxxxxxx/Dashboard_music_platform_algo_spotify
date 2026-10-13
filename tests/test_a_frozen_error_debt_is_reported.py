"""A catalogue debt that stops falling is reported every night — the ACTIONABLE debt.

Type: Sub
Uses: tools/dev/error_debt_trend.py (frozen, actionable_debt), tools/dev/error_debt.py
      (work_list — the population `make error-debt` prints), .github/workflows/security-nightly.yml
Depends on: tools/dev/generated_cache.py (health payload of this tree, R345) — no database

R562 (2026-10-13): the nightly `debt-trend` judged `guard_does_not_prove_itself` (18, frozen)
while `make error-debt`, the list it points the reader to, printed « 0 classe à traiter ».
Two readers of one debt counted two populations, so the check could never pass again.
"""
import importlib.util
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "tools" / "dev"))
import generated_cache  # noqa: E402


_spec = importlib.util.spec_from_file_location("edt", _ROOT / "tools/dev/error_debt_trend.py")
edt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(edt)
_spec = importlib.util.spec_from_file_location("error_debt_for_trend",
                                               _ROOT / "tools/dev/error_debt.py")
debt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(debt)


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """A stuck actionable debt is frozen; a fall and an older schema are not."""
    stuck = {"actionable_debt": 3, "guard_does_not_prove_itself": 306}
    assert edt.frozen(stuck, dict(stuck)), "nothing fell: frozen"
    assert not edt.frozen(stuck, {**stuck, "actionable_debt": 2})
    assert edt.frozen(stuck, {**stuck, "actionable_debt": 4}), "a rise is not a fall"
    assert not edt.frozen({"other": 1}, stuck), "no common key: nothing can be concluded"


def test_a_paid_debt_is_not_frozen() -> None:
    """The 2026-10-13 nightly: 0 actionable, 18 guards not self-proving, nothing moved."""
    nightly = {"actionable_debt": 0, "guard_does_not_prove_itself": 18, "cause_unknown": 0,
               "seen_red_unknown": 0}
    assert not edt.frozen(nightly, dict(nightly)), (
        "a debt `make error-debt` lists as EMPTY was reported frozen — the counter judged "
        "is not the one the list prints (R562)")


def test_the_trend_and_error_debt_count_the_same_population() -> None:
    """`debt-trend` judges exactly the classes `make error-debt` lists, on this tree."""
    text = (_ROOT / ".claude/dev-docs/error-classes.md").read_text(encoding="utf-8")
    listed = debt.work_list(generated_cache.health_payload()["classes"],
                            debt.recurrences(text), 10_000)
    assert edt.JUDGED == ("actionable_debt",)
    assert edt.actionable_debt(text) == len(listed), (
        f"`make error-debt` lists {len(listed)} class(es), `error_debt_trend.py` judges "
        f"{edt.actionable_debt(text)}: two populations for one debt (R562)")


def test_the_nightly_runs_it_and_mails_it() -> None:
    wf = yaml.safe_load((_ROOT / ".github/workflows/security-nightly.yml").read_text(encoding="utf-8"))
    assert "error_debt_trend.py" in str(wf["jobs"]["debt-trend"]["steps"])
    assert "debt-trend" in wf["jobs"]["notify"]["needs"]
