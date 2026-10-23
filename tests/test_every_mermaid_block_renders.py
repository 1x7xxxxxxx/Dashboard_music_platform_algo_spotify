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
import os
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
    # R495 — `== 1`, not `!= 0`: exit 2 is « mmdc could not run », a crash, and must not
    # pass as the detector having SEEN the malformed block.
    assert cm.main() == 1


def test_the_nvm_fallback_runs_without_node_on_path(monkeypatch) -> None:
    """R643 — `make test` outside a login shell (fleet-verify, cron): nvm's bin is not on
    PATH, `_mmdc()` finds mmdc by its nvm glob, and the run used to exit 2 on
    `env: 'node': No such file or directory` — a launch crash on 3 valid diagrams."""
    exe = cm._mmdc()
    keep = [d for d in os.environ.get("PATH", "").split(os.pathsep)
            if d and not (Path(d) / "node").exists() and not (Path(d) / "mmdc").exists()]
    monkeypatch.setenv("PATH", os.pathsep.join(keep))
    if cm._mmdc() is None:
        pytest.skip(f"mmdc at {exe} is only reachable through PATH — no fallback to exercise")
    assert cm.main() == 0, "mmdc found by the nvm fallback could not run without node on PATH"
