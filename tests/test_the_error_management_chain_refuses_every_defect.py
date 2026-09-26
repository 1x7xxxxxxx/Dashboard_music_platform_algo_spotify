"""The error-class chain still refuses what it exists to refuse — the cheap, per-commit half.

Type: Sub
Uses: tools/dev/probe_error_management.py (unwired, insert_class, CONTROL, PROBES),
      .claude/scripts/audit_runner.py (proof_gaps), .github/workflows/ci.yml,
      .github/workflows/security-nightly.yml
Depends on: nothing
Persists in: nothing

R184 (2026-09-26). The full probe (`make error-management-probe`, nightly job
`error-management-probe`) runs every gate against a fabricated class in a scratch worktree —
minutes, so not per commit. What a commit CAN break cheaply is checked here:
- a gate unwired from `ci.yml` refuses nothing, while its tests stay green;
- the probe's control class must be valid, or every « refused » it reports is noise;
- every probe that targets the per-class proofs (R185) is refused by `proof_gaps`;
- the nightly job exists and reaches the owner (`notify` needs it).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


probe = _load("probe_error_management", "tools/dev/probe_error_management.py")
runner = _load("audit_runner_for_probe", ".claude/scripts/audit_runner.py")


def _header(fields: dict) -> dict:
    return {"id": probe.CID, **{k: v for k, v in fields.items() if v is not None}}


def _ci_commands() -> str:
    """Every `run:` of ci.yml, parsed — the gates are what the steps RUN, not what a comment says."""
    wf = yaml.safe_load((_ROOT / ".github" / "workflows" / "ci.yml").open(encoding="utf-8"))
    return "\n".join(s.get("run") or "" for job in wf["jobs"].values()
                     for s in job.get("steps", []))


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """A ci.yml that no longer runs the admission gate is named; the real one is complete."""
    real = _ci_commands()
    assert probe.unwired(real) == []
    assert probe.unwired(real.replace("audit_runner.py --admission", "true")) == ["admission"]


def test_the_control_class_is_valid() -> None:
    assert runner.proof_gaps(_header(probe.CONTROL)) == []
    text = probe.insert_class("## Index\n\n| CLASS-ID | sev | kind | status | autofix |\n"
                              "|---|---|---|---|---|\n", probe.CONTROL)
    assert f"[{probe.CID}](#{probe.CID})" in text and f"## {probe.CID}" in text


def test_every_proof_probe_is_refused_by_the_admission_gate() -> None:
    proof_fields = {"siblings", "root_cause", "cause_evidence", "seen_red"}
    targeted = [p for p in probe.PROBES if set(p.breaks) & proof_fields
                and "ceiling" not in p.guaranteed_by and "self-proving" not in p.name
                and "missing test" not in p.name and "inferred" != p.breaks.get("cause_evidence")]
    assert len(targeted) >= 6, "the probe list lost its proof probes"
    for p in targeted:
        assert runner.proof_gaps(_header({**probe.CONTROL, **p.breaks})), p.name


def test_the_nightly_probe_runs_and_reaches_the_owner() -> None:
    wf = yaml.safe_load((_ROOT / ".github" / "workflows" / "security-nightly.yml").open(
        encoding="utf-8"))
    job = wf["jobs"]["error-management-probe"]
    run = "\n".join(s.get("run") or "" for s in job["steps"])
    assert "probe_error_management.py" in run
    # Without installed git hooks the terminal-commit probe has nothing to refuse it — the
    # first CI run said exactly that (2026-09-26).
    assert run.index("pre-commit install") < run.index("probe_error_management.py")
    assert "error-management-probe" in wf["jobs"]["notify"]["needs"]
