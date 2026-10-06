"""R428 — the « Rapport PDF » page does not change unless a roadmap row says it must.

Type: Test
Uses: tests/pdf_report_snapshot.py (the frozen render), tools/dev/require_roadmap_id.py (the lock)
Depends on: tests/fixtures/pdf_report_snapshot.json
Persists in: nothing

The owner, 2026-10-06: « vérrouille la view de rapport de carrière pdf ». Same two halves
as Home (tests/test_home_is_frozen.py): the PHOTO, and the LOCK on approving a new one.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools/dev"))

from require_roadmap_id import PDF_REPORT_LOCKED, verdict  # noqa: E402
from tests import pdf_report_snapshot  # noqa: E402
from tests.test_home_is_frozen import _first_difference  # noqa: E402


@pytest.mark.xdist_group("pdf_report_frozen")
@pytest.mark.parametrize("scenario", sorted(pdf_report_snapshot.SCENARIOS))
def test_the_pdf_report_renders_exactly_the_approved_photo(scenario: str) -> None:
    approved = json.loads(pdf_report_snapshot.PHOTO.read_text(encoding="utf-8"))[scenario]
    got = pdf_report_snapshot.render(scenario)
    assert got == approved, (
        f"Le Rapport PDF ({scenario}) a changé — first difference at "
        f"{_first_difference(approved, got)}.\n"
        "If this change was made for ANOTHER page, it leaked in through a shared helper: "
        "keep the report page as it was. If it must change, run `make pdf-report-snapshot` "
        "and commit the photo under a roadmap row carrying `<!-- rapport_pdf: oui -->`.")


_CHECKLIST = ("## 📋 Tâches ouvertes\n\n| ID | Tâche | P | Mesure |\n|---|---|---|---|\n"
              "| R900 | Rapport PDF : x <!-- critic: non — x --> {marker}| P3 | x |\n")


def _verdict(marker: str, files=PDF_REPORT_LOCKED) -> str | None:
    return verdict(list(files), "R900 : nouvelle photo", _CHECKLIST.format(marker=marker))


def test_a_new_photo_without_its_marker_is_refused() -> None:
    for f in PDF_REPORT_LOCKED:
        assert "rapport_pdf: oui" in (_verdict("", files=(f,)) or ""), f


def test_the_home_marker_does_not_unlock_the_report() -> None:
    """Each page has ITS marker: a row allowed to touch Home is not allowed here."""
    assert _verdict("<!-- home: oui --> ") is not None


def test_a_new_photo_under_a_row_marked_rapport_pdf_goes() -> None:
    assert _verdict("<!-- rapport_pdf: oui --> ") is None
