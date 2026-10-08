"""R472 — a commit touching a collector runs the collector audit; nothing nags for it.

Type: Test
Uses: .pre-commit-config.yaml, tools/dev/arch_benchmark.py (live_suggestion_surfaces,
      still_suggested, manual_invocation)
Depends on: nothing live
Persists in: nothing

Rule 6 said « run /audit-collectors after touching any collector » and the bug-resolution
playbook printed it: 0 runs in 44 sessions. What must hold:
1. a pre-commit hook fires on `src/collectors/*.py` and runs BOTH mechanical audits —
   R1 (`audit_collectors_ast.py`, raise in except) and R4 (`audit_tenant_writes.py`);
2. no live hook or injected playbook prints `/audit-collectors` any more;
3. the command declares `invocation: manual` — its R2/R3 are judgment, not a nag.

Mutation record (2026-10-08): seen red with the hook's `files:` pointed at `src/utils/`,
with the R4 script dropped from `entry`, and with `/audit-collectors` put back in
bug-resolution.md.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("arch_benchmark_r472", ROOT / "tools/dev/arch_benchmark.py")
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)


def _hook() -> dict:
    cfg = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hooks = [h for repo in cfg["repos"] for h in repo.get("hooks", []) if h["id"] == "collector-audit"]
    assert len(hooks) == 1, "the pre-commit hook collector-audit is missing"
    return hooks[0]


def test_a_collector_change_triggers_both_mechanical_audits() -> None:
    h = _hook()
    files = re.compile(h["files"])
    assert files.search("src/collectors/spotify_api.py")
    assert not files.search("src/dashboard/app.py")
    assert "audit_collectors_ast.py" in h["entry"] and "audit_tenant_writes.py" in h["entry"]
    for script in ("audit_collectors_ast.py", "audit_tenant_writes.py"):
        assert (ROOT / ".claude" / "scripts" / script).is_file(), script


def test_no_live_surface_nags_for_the_command() -> None:
    surfaces = bench.live_suggestion_surfaces()
    assert not bench.still_suggested("audit-collectors", surfaces), (
        [k for k, v in surfaces.items() if "/audit-collectors" in v])
    # non-vacuity: the detector sees the nag it is written for
    assert bench.still_suggested("audit-collectors", {"x.md": "run `/audit-collectors` now"})


def test_the_command_is_declared_manual() -> None:
    assert bench.manual_invocation(".claude/commands/audit-collectors.md")
