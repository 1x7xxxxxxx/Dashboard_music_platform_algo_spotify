"""A dependency audit reads the set the CI INSTALLS, not the constraints it starts from.

Type: Sub
Uses: .github/workflows/*.yml (read as YAML)
Depends on: nothing
Persists in: nothing

Class `audit-reads-the-constraints-not-the-installed-set`: the nightly ran
`pip-audit -r requirements.txt`. That file carries FLOORS (`cryptography>=42.0.0`), so
pip-audit resolved recent versions and reported clean — while the CI installed `uv.lock`
through `uv sync --frozen`, which pinned older ones. The class signature grepped for the
one literal command; this file asks the property: every requirements file handed to
`pip-audit -r` is written, earlier in the same job, by `uv export` from the lock.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

_WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
_AUDITED = re.compile(r"pip-audit\b[^\n]*?\s-r\s+(\S+)")
_EXPORTED = re.compile(r"uv export\b[^\n]*?(?:\s-o\s+|--output-file[= ]|>\s*)(\S+)")


def audits_of_constraints(workflow: dict) -> list[str]:
    """`job: file` for every `pip-audit -r <file>` whose file no EARLIER step of the
    same job — or an earlier LINE of the same step — wrote with `uv export`. Pure."""
    out = []
    for name, job in ((workflow or {}).get("jobs") or {}).items():
        exported: set[str] = set()
        for step in (job or {}).get("steps") or []:
            # Line by line, in order: an export and its audit may share one script.
            for line in str((step or {}).get("run") or "").splitlines():
                out += [f"{name}: {a}" for a in _AUDITED.findall(line) if a not in exported]
                exported |= set(_EXPORTED.findall(line))
    return out


def test_every_audit_reads_the_exported_lock() -> None:
    files = sorted(_WORKFLOWS.glob("*.y*ml"))
    offenders = [f"{p.name} → {hit}" for p in files
                 for hit in audits_of_constraints(yaml.safe_load(p.read_text(encoding="utf-8")))]
    assert not offenders, (
        f"{offenders} : `pip-audit -r` lit un fichier que `uv export` n'a pas écrit dans "
        "le même job. Des planchers (`>=`) font auditer des versions récentes pendant que "
        "la CI installe le lock : le rapport est propre sur ce qui ne tourne pas. "
        "Exporter d'abord : `uv export --frozen --no-dev --no-hashes -o audited.txt`.")


def test_the_scan_still_sees_the_nightly_audit() -> None:
    nightly = yaml.safe_load((_WORKFLOWS / "security-nightly.yml").read_text(encoding="utf-8"))
    runs = " ".join(str(s.get("run") or "") for j in nightly["jobs"].values()
                    for s in j.get("steps") or [])
    assert _AUDITED.search(runs), "the nightly no longer runs `pip-audit -r` — this guard sees nothing"


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: the nightly of before 2026-09 — `pip-audit -r requirements.txt` —
    is named; so is an audit that runs BEFORE its export; the export-then-audit order
    passes, with `-o` and with a shell redirection alike."""
    old = {"jobs": {"pip-audit": {"steps": [
        {"run": "pip install pip-audit"},
        {"run": "pip-audit -r requirements.txt --desc on"},
        {"run": "pip-audit -r requirements.txt --format json -o report.json"}]}}}
    assert audits_of_constraints(old) == ["pip-audit: requirements.txt"] * 2
    late = {"jobs": {"a": {"steps": [
        {"run": "pip-audit -r audited.txt"},
        {"run": "uv export --frozen --no-dev -o audited.txt"}]}}}
    assert audits_of_constraints(late) == ["a: audited.txt"]
    good = {"jobs": {"a": {"steps": [
        {"run": "uv export --frozen --no-dev --no-hashes -o audited.txt"},
        {"run": "pip-audit -r audited.txt --desc on"}]},
        "b": {"steps": [{"run": "uv export --frozen > locked.txt\npip-audit -r locked.txt"}]}}}
    assert audits_of_constraints(good) == []
