"""Every P1 error class runs every night, and a P1 that nothing executes turns the job red.

Type: Sub
Uses: .claude/scripts/audit_runner.py (unguarded_classes), .github/workflows/security-nightly.yml
Depends on: nothing — fabricated catalogue headers

2026-09-25: an impact analysis cannot be automated (a hook cannot spawn an agent), but the
KNOWN critical classes can be. The first run found one P1 guarded by nothing but prose.
"""
import importlib.util
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / ".claude/scripts"))
_spec = importlib.util.spec_from_file_location("audit_runner_p1", _ROOT / ".claude/scripts/audit_runner.py")
ar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ar)


def _h(cid, sev="P1", sig=None, guard=None):
    return {"id": cid, "severity": sev, "signature": sig, "guard": guard}


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    headers = [
        _h("prose-only", guard="{ type: doc-convention, ref: migrations/065_x.sql }"),
        _h("dead-guard-path", guard="tests/test_that_was_deleted.py::test_x"),
        _h("has-signature", sig="! grep -rn foo src/"),
        _h("has-live-guard", guard="tests/test_the_p1_classes_are_guarded_every_night.py"),
        _h("p2-prose", sev="P2"),
    ]
    assert ar.unguarded_classes(headers, "P1") == ["prose-only", "dead-guard-path"]


def test_the_nightly_runs_the_p1_pass_and_mails_it() -> None:
    wf = yaml.safe_load((_ROOT / ".github/workflows/security-nightly.yml").read_text(encoding="utf-8"))
    job = wf["jobs"]["p1-classes"]
    assert "--severity P1" in str(job["steps"])
    assert "p1-classes" in wf["jobs"]["notify"]["needs"]
