"""`make audit-deps` never passes on a report its producer did not write (R660).

Type: Sub
Uses: Makefile (audit-deps, check-pipaudit), tools/dev/pip_audit_gate.py
Depends on: nothing at runtime — reads the recipe and calls the gate on a temp path
Persists in: nothing

On 2026-10-26 `make audit-deps` printed ✅ while pip-audit could not start (the
`.audit-venv` shebang named the repo's old path): the producer's `|| true` swallowed
the failure and the gate re-read `.pip-audit.json` from 2026-10-04.

guard_scope: the audit-deps recipe (report removed before the producer runs, the gate
refusing a missing/empty report) and check-pipaudit executing the binary.
NOT covered: other `producer || true ; reader file` pairs in the Makefile (the sweep of
2026-10-26 found none live), and the nightly workflow (a fresh runner, no stale file).
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("pip_audit_gate", ROOT / "tools/dev/pip_audit_gate.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def _recipe(target: str) -> list[str]:
    lines, out, inside = (ROOT / "Makefile").read_text(encoding="utf-8").splitlines(), [], False
    for ln in lines:
        if re.match(rf"^{re.escape(target)}:", ln):
            inside = True
            continue
        if inside and not ln.startswith("\t"):
            break
        if inside and not ln.lstrip("\t@").startswith("#"):
            out.append(ln.strip().lstrip("@"))
    return out


def test_the_gate_refuses_a_missing_report(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pip_audit_gate.py", str(tmp_path / "absent.json")])
    assert gate.main() != 0


def test_the_gate_refuses_an_empty_report(tmp_path, monkeypatch):
    empty = tmp_path / "empty.json"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["pip_audit_gate.py", str(empty)])
    assert gate.main() != 0


def test_audit_deps_removes_the_previous_report_before_producing_it():
    steps = _recipe("audit-deps")
    produce = next(i for i, s in enumerate(steps) if "$(PIP_AUDIT)" in s and "-o .pip-audit.json" in s)
    removes = [i for i, s in enumerate(steps) if re.search(r"\brm\b.*\.pip-audit\.json", s)]
    assert removes and min(removes) < produce, steps


def test_check_pipaudit_executes_the_binary_not_only_stats_it():
    steps = " ".join(_recipe("check-pipaudit"))
    assert "$(PIP_AUDIT) --version" in steps
    assert "test -x" not in steps
