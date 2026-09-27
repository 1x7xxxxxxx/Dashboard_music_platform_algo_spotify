#!/usr/bin/env python3
"""Fail on any pip-audit advisory that is not explicitly accepted.

Type: Utility
Uses: a pip-audit JSON report, security/pip-audit-accepted.txt
Triggers: .github/workflows/security-nightly.yml (pip-audit job)
Persists in: nothing

R267 (owner notes L138/L170 ; critic a) — the nightly audit was observational (`|| true`,
then a count in a mail): 58 advisories rode every night and a 59th would have looked the
same. Now the known ones are NAMED with their reason, and a new one fails the job.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACCEPTED = ROOT / "security" / "pip-audit-accepted.txt"


def accepted_ids(text: str) -> set[str]:
    return {ln.split()[0] for ln in text.splitlines() if ln.strip() and not ln.startswith("#")}


def unaccepted(report: dict, accepted: set[str]) -> list[str]:
    """`<id> <package> <version>` of every advisory not in `accepted`. Pure."""
    return sorted({f"{v['id']} {d['name']} {d.get('version', '?')}"
                   for d in report.get("dependencies", []) for v in d.get("vulns", [])
                   if v["id"] not in accepted and not set(v.get("aliases", [])) & accepted})


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: pip_audit_gate.py <pip-audit.json>", file=sys.stderr)
        return 2
    report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    new = unaccepted(report, accepted_ids(ACCEPTED.read_text(encoding="utf-8")))
    if new:
        print(f"❌ {len(new)} advisory(ies) not accepted in {ACCEPTED.relative_to(ROOT)}:")
        for line in new:
            print(f"   {line}")
        return 1
    print("✅ every advisory is fixed or accepted with its reason")
    return 0


if __name__ == "__main__":
    sys.exit(main())
