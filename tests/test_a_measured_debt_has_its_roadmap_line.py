"""A debt the repository can MEASURE has an anchored line in the active roadmap's index.

Type: Sub
Uses: tools/dev/error_debt.py, .claude/dev-docs/roadmap/checklist.md
Depends on: the committed error-class-health.json — no database

Measured 2026-09-25: nothing made an identified action ENTER the roadmap — the mechanisms
handle the exit (rotation) and consistency, never the entry; ~9 actions identified that
day, 0 written. A hook cannot see an action the model forgot to write (code-critic). What
it CAN see is a quantity the repository measures itself: while `make error-debt` has work
to list, the index must carry the row anchored `<!-- anchor: error-debt -->`.
"""
import importlib.util
import json
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_CHECKLIST = _ROOT / ".claude/dev-docs/roadmap/checklist.md"
_spec = importlib.util.spec_from_file_location("error_debt", _ROOT / "tools/dev/error_debt.py")
debt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(debt)

_ANCHOR = "<!-- anchor: error-debt -->"


def _index(text: str) -> str:
    """The `## 📋 Tâches ouvertes` section — the only place an anchor counts as open work."""
    m = re.search(r"^## 📋 Tâches ouvertes.*?(?=^## )", text, re.M | re.S)
    return m.group(0) if m else ""


def _missing_line(open_items: int, checklist_text: str) -> bool:
    rows = [ln for ln in _index(checklist_text).splitlines() if ln.startswith("| R")]
    return open_items > 0 and not any(_ANCHOR in ln for ln in rows)


def test_the_measured_debt_is_on_the_roadmap() -> None:
    health = json.loads((_ROOT / ".claude/dev-docs/error-class-health.json").read_text(encoding="utf-8"))
    items = debt.work_list(health["classes"],
                           debt.recurrences((_ROOT / ".claude/dev-docs/error-classes.md").read_text(encoding="utf-8")),
                           10_000)
    assert not _missing_line(len(items), _CHECKLIST.read_text(encoding="utf-8")), (
        f"`make error-debt` lists {len(items)} class(es) to pay down, and no row of the "
        f"roadmap index carries `{_ANCHOR}`. A measured debt with no line is a debt nobody "
        "is working on — add the row (or pay the debt).")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """The checklist of 2026-09-25 afternoon — empty index, debt measured — must be refused."""
    empty_index = "## 📋 Tâches ouvertes\n\n| id | Tâche |\n|---|---|\n\n## next\n"
    assert _missing_line(5, empty_index)
    anchored = ("## 📋 Tâches ouvertes\n\n| R169 | Dette " + _ANCHOR + " | P3 |\n\n## next\n")
    assert not _missing_line(5, anchored)
    assert not _missing_line(0, empty_index), "no debt, no line required"
    elsewhere = "## 📋 Tâches ouvertes\n\n| id |\n\n## Archive\n| R1 | " + _ANCHOR + " |\n"
    assert _missing_line(5, elsewhere), "an anchor OUTSIDE the open index is not open work"
