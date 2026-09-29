"""Every mermaid block under .claude/dev-docs/ renders — run by the suite, not only by hand.

Type: Sub
Uses: .claude/scripts/check_mermaid.py (mmdc)
Depends on: `mmdc` (@mermaid-js/mermaid-cli) — skipped, and said, where it is not installed

R327 (2026-09-29): class `mermaid-block-does-not-render` was guarded by `make audit`, whose
recipe runs `check_mermaid.py || true` — it can never fail. The catalogue counted it as
`prose_only`, correctly. Where mmdc exists (this workstation), the check now runs with the
suite; where it does not (CI), the skip reason says so instead of a silent green.

Mutation record (2026-09-29): seen red with an invalid ```mermaid``` block added to a scratch
copy of the dev-docs (the check's own `_ROOTS` pointed at it).
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("check_mermaid",
                                               ROOT / ".claude/scripts/check_mermaid.py")
cm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cm)

pytestmark = pytest.mark.skipif(cm._mmdc() is None,
                                reason="mmdc absent — mermaid blocks NOT validated here")


def test_every_block_renders() -> None:
    assert cm.main() == 0, "a mermaid block under .claude/dev-docs/ does not render"


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path, monkeypatch) -> None:
    (tmp_path / "bad.md").write_text("# x\n\n```mermaid\ngantt\n  not mermaid ((((\n```\n")
    monkeypatch.setattr(cm, "_ROOTS", (tmp_path,))
    monkeypatch.setattr(cm, "_REPO", tmp_path)
    assert cm.main() != 0
