"""Two error-class checks that had no guard of their own (R186, 2026-09-26 audit).

Type: Sub
Uses: .claude/scripts/audit_runner.py (_hit_is_prose), .claude/hooks/check_error_class_evidence.py
Depends on: nothing
Persists in: nothing

`audit_runner --prose` (ci.yml) refuses a deterministic signature whose hits all land on
comments or documents — a class that turns red on the prose explaining its own fix. The
PostToolUse hook `check_error_class_evidence.py` warns, at the moment a class is written,
when one lacks its proofs. Neither had a test: a predicate edited into blindness, or a hook
whose field list rotted, would have gone unnoticed.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("audit_runner_prose",
                                               _ROOT / ".claude/scripts/audit_runner.py")
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)
_HOOK = _ROOT / ".claude/hooks/check_error_class_evidence.py"


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """A hit on a comment or a document is prose; a hit on code is not."""
    assert runner._hit_is_prose("src/a.py:12:    # datetime.now() is naive here") is True
    assert runner._hit_is_prose("docs/guide.md:3:datetime.now()") is True
    assert runner._hit_is_prose("src/a.py:12:    cutoff = datetime.now()") is False


def _warn(tmp_path: Path, body: str) -> str:
    cat = tmp_path / "error-classes.md"
    cat.write_text("# catalogue\n\n## a-fabricated-class\n" + body, encoding="utf-8")
    return subprocess.run([sys.executable, str(_HOOK)], input=json.dumps(
        {"tool_input": {"file_path": str(cat)}}), capture_output=True, text=True,
        timeout=30).stderr


def test_the_evidence_hook_names_a_class_without_its_proofs(tmp_path) -> None:
    missing = _warn(tmp_path, "- status: guarded\n- seen_red: never — no fixture\n")
    assert "a-fabricated-class" in missing and "siblings" in missing
    complete = _warn(tmp_path, "- status: guarded\n- seen_red: 2026-09-26\n"
                               "- cause_evidence: read (src/a.py)\n- guard_scope: x ; ne couvre pas: y\n"
                               "- siblings: swept:2026-09-26 — **0 site vivant**\n")
    assert "a-fabricated-class" not in complete
