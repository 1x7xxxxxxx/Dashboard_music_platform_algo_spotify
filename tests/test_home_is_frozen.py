"""R425 — Home does not change unless a roadmap row says Home must change.

Type: Test
Uses: tests/home_snapshot.py (the frozen render), tools/dev/require_roadmap_id.py (the lock)
Depends on: tests/fixtures/home_data.pkl, tests/fixtures/home_snapshot.json
Persists in: nothing

The owner, 2026-10-06: « trouver une solution pour ne plus toucher la page d'accueil,
parce que beaucoup de fois j'ai eu le cas où je modifiais un truc sur une page et il y
avait l'autre page qui était modifiée ». Two halves:

* the PHOTO: Home rendered on recorded data, compared to the approved one — a change
  made for another page through a shared helper turns this red;
* the LOCK: approving a new photo is refused by the commit-msg hook unless a cited open
  roadmap row carries `<!-- home: oui -->`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools/dev"))

from require_roadmap_id import HOME_LOCKED, verdict  # noqa: E402
from tests import home_snapshot  # noqa: E402


def _first_difference(want, got, path="") -> str:
    if type(want) is not type(got):
        return f"{path or '/'}: {str(want)[:200]!r} → {str(got)[:200]!r}"
    if isinstance(want, dict):
        for k in sorted(set(want) | set(got)):
            if want.get(k) != got.get(k):
                return _first_difference(want.get(k), got.get(k), f"{path}/{k}")
    if isinstance(want, list):
        if len(want) != len(got):
            return f"{path}: {len(want)} elements → {len(got)}"
        for i, (a, b) in enumerate(zip(want, got)):
            if a != b:
                return _first_difference(a, b, f"{path}[{i}]")
    return f"{path or '/'}: {str(want)[:200]!r} → {str(got)[:200]!r}"


@pytest.mark.xdist_group("home_frozen")
@pytest.mark.parametrize("scenario", sorted(home_snapshot.SCENARIOS))
def test_home_renders_exactly_the_approved_photo(scenario: str) -> None:
    approved = json.loads(home_snapshot.PHOTO.read_text(encoding="utf-8"))[scenario]
    data = home_snapshot.load_data()[home_snapshot.TOGGLED_OFF.get(scenario, scenario)]
    got = home_snapshot.render(scenario, data)
    got = json.loads(json.dumps(got, ensure_ascii=False, sort_keys=True))
    assert got == approved, (
        f"L'Accueil ({scenario}) a changé — first difference at "
        f"{_first_difference(approved, got)}.\n"
        "If this change was made for ANOTHER page, it leaked into Home through a shared "
        "helper: keep Home as it was. If Home must change, run `make home-snapshot` and "
        "commit the photo under a roadmap row carrying `<!-- home: oui -->`.")


_ROW = "| R900 | Accueil : quelque chose <!-- critic: non — x --> {marker}| P3 | x |"
_CHECKLIST = "## 📋 Tâches ouvertes\n\n| ID | Tâche | P | Mesure |\n|---|---|---|---|\n{row}\n"


def _verdict(marker: str, files=("tests/fixtures/home_snapshot.json",)) -> str | None:
    checklist = _CHECKLIST.format(row=_ROW.format(marker=marker))
    return verdict(list(files), "R900 : nouvelle photo", checklist)


def test_a_new_photo_without_the_home_marker_is_refused() -> None:
    assert "home: oui" in (_verdict("") or "")
    # The word "Accueil" in the row is not the marker: half the rows name a page.
    assert _verdict("") is not None


def test_a_new_photo_under_a_row_marked_home_goes() -> None:
    assert _verdict("<!-- home: oui --> ") is None


def test_every_locked_file_is_guarded_and_other_tests_are_not() -> None:
    for f in HOME_LOCKED:
        assert _verdict("", files=(f,)) is not None, f
    assert _verdict("", files=("Makefile",)) is None


def test_a_photo_with_no_recorded_answer_names_the_missing_reader() -> None:
    """The replay must fail loud, never fall through to a database CI does not have."""
    with pytest.raises(AssertionError, match="REPLAYED|home-record"):
        home_snapshot.render("full", {})
