"""The coverage map reads a class's `guard:` field WHOLE, never its display cut.

Type: Sub
Uses: tools/dev/gold_coverage.py (scan_error_classes)
Depends on: nothing
Persists in: nothing

2026-09-26 (R180). `scan_error_classes` stored `guard[:90]` — a cut meant for a table cell —
and the `plateforme × famille` matrix extracted guard paths from it. Every guard named
after the first 90 characters was invisible: two cells (Spotify S4A and YouTube ×
`le-locataire`) read EMPTY while their guard existed. An instrument that under-counts
what it measures sends people to write guards that already exist.
"""
from __future__ import annotations

from tools.dev import gold_coverage as g


def _scan(tmp_path, monkeypatch, guard: str):
    doc = tmp_path / "error-classes.md"
    doc.write_text(f"## some-class\n- status: guarded\n- guard: {guard}\n", encoding="utf-8")
    monkeypatch.setattr(g, "_CLASSES_DOC", doc)
    return g.scan_error_classes()[0].guard


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path, monkeypatch) -> None:
    """A second guard named past character 90 survives the scan."""
    second = "tests/test_a_gold_view_is_blind_to_another_tenants_rows.py"
    guard = ("{ type: pytest, ref: tests/test_a_quantity_is_summed_and_names_its_tenant.py"
             f"::test_every_read_of_these_relations_names_its_tenant + {second} }}")
    assert len(guard) > 90 and guard.index(second) > 90
    assert second in _scan(tmp_path, monkeypatch, guard)
