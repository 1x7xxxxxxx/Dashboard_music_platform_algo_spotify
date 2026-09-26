"""`gold_coverage.py --check` refuses a document that no longer says what the repo says.

Type: Sub
Uses: tools/dev/gold_coverage.py (main --check)
Depends on: nothing — `build()` is replaced by a fixed string, the document by a tmp file

Class `a-generated-document-asserts-a-stale-state`: a generated document carries no mark
of age, so a stale one reads exactly like a fresh measure.
"""
import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "gold_coverage_check", Path(__file__).resolve().parents[1] / "tools/dev/gold_coverage.py")
gc = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = gc   # dataclasses resolve their module by name
_spec.loader.exec_module(gc)


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path, monkeypatch) -> None:
    """A document that differs from what `build()` would write is refused; the same text
    passes; an ABSENT document is refused too (absence is not freshness)."""
    doc = tmp_path / "gold-coverage.md"
    monkeypatch.setattr(gc, "DOC", doc)
    monkeypatch.setattr(gc, "build", lambda: "# carte\nv_platform_levels : or\n")
    monkeypatch.setattr(sys, "argv", ["gold_coverage.py", "--check"])
    assert gc.main() == 1, "an absent document must not pass"
    doc.write_text("# carte\nv_platform_levels : brut\n", encoding="utf-8")
    assert gc.main() == 1, "a stale document must not pass"
    doc.write_text("# carte\nv_platform_levels : or\n", encoding="utf-8")
    assert gc.main() == 0
