"""R267 (critic a) — the nightly audit BLOCKS on an advisory nobody accepted.

Type: Test
Uses: tools/dev/pip_audit_gate.py, security/pip-audit-accepted.txt,
      .github/workflows/security-nightly.yml

Measured 2026-09-28: 58 advisories rode the nightly mail, 57 from the Airflow 2.11 stack
(fix = Airflow 3), one fixable (WeasyPrint 69 → 70, upgraded). The accepted ones are now
NAMED with their reason; a new one fails the job, and gitleaks blocks too (0 finding on the
whole history).

Mutation record (2026-09-28) : `unaccepted` ignoring the accepted set → red ; the gate
step removed from the workflow → red ; `continue-on-error` put back on gitleaks → red.
"""
import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("pip_audit_gate", ROOT / "tools/dev/pip_audit_gate.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def test_only_an_unaccepted_advisory_is_reported():
    report = {"dependencies": [
        {"name": "apache-airflow", "version": "2.11.2", "vulns": [{"id": "PYSEC-A", "aliases": []}]},
        {"name": "lib", "version": "1.0", "vulns": [{"id": "PYSEC-NEW", "aliases": ["GHSA-x"]}]},
        {"name": "ok", "version": "2.0", "vulns": []}]}
    assert gate.unaccepted(report, {"PYSEC-A"}) == ["PYSEC-NEW lib 1.0"]
    assert gate.unaccepted(report, {"PYSEC-A", "GHSA-x"}) == [], "an alias counts"


def test_every_accepted_line_carries_a_reason_not_vacuous():
    text = (ROOT / "security" / "pip-audit-accepted.txt").read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    assert lines, "the accepted list is no longer read"
    assert all(" — " in ln and len(ln.split(" — ", 1)[1]) >= 10 for ln in lines)


def test_the_nightly_blocks_on_audit_and_on_leaks():
    wf = yaml.safe_load((ROOT / ".github/workflows/security-nightly.yml").read_text(encoding="utf-8"))
    audit, leaks = wf["jobs"]["pip-audit"], wf["jobs"]["gitleaks"]
    assert not audit.get("continue-on-error") and not leaks.get("continue-on-error")
    assert any("pip_audit_gate.py" in (s.get("run") or "") for s in audit["steps"])
    assert any("requirements-api.txt" in (s.get("run") or "") for s in audit["steps"])
    scan = next(s for s in leaks["steps"] if s.get("id") == "scan")
    assert not scan.get("continue-on-error")


def test_the_accepted_list_carries_a_recheck_date_not_yet_past():
    """REQ-SEC-06 — no advisory is ignored by name without an end: the list says when it
    is re-checked, and a date in the past fails."""
    import datetime
    import re
    text = (ROOT / "security" / "pip-audit-accepted.txt").read_text(encoding="utf-8")
    m = re.search(r"recheck-by:\s*(\d{4}-\d{2}-\d{2})", text)
    assert m, "no `recheck-by:` date in the accepted list"
    assert datetime.date.fromisoformat(m.group(1)) >= datetime.date.today(), (
        "the accepted advisories are past their re-check date — re-audit them")
