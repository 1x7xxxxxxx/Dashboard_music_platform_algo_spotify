#!/usr/bin/env python3
"""Nightly sweep of every PUBLIC surface where a secret of this owner could be read.

Type: Utility
Uses: GitHub REST API (GITHUB_TOKEN), git, gitleaks (tools/dev/install_gitleaks.sh)
Triggers: .github/workflows/security-nightly.yml, job `public-surface-sweep`
Persists in: nothing — prints counts (never a value), exit 1 when a surface leaks

On 2026-09-25 the impact analysis of the gitleaks findings (12 real secrets in this public
repo's history) was done BY HAND, after the owner asked — no hook can spawn an agent, and
the triage had been framed as security, not as a defect class. Its perimeters were
mechanical, so they are a machine's job now, every night:

  1. every OTHER public repository of the owner — full history, gitleaks;
  2. forks of this repository — a fork keeps the history this repo may rewrite;
  3. the logs of this repository's recent Actions runs — public on a public repo —
     for `SECRET|KEY|PASSWORD|TOKEN = <value>` lines GitHub did not mask.

This repository's own history is the `gitleaks` job's; it is not scanned twice.
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import tempfile
import urllib.request
import zipfile

_API = os.environ.get("GITHUB_API_URL", "https://api.github.com")
_ASSIGN = re.compile(r"\b[A-Z0-9_]*(SECRET|API_KEY|PASSWORD|TOKEN)[A-Z0-9_]*\s*[:=]\s*['\"]?([^\s'\"]{8,})")
# Values that are fabricated on purpose in this repo's workflows, or masked by GitHub.
# gitleaks colours its REDACTED placeholder: without this, 18 masked lines read as leaks.
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_KNOWN_FAKE = re.compile(r"^(\*{3}|REDACTED|ci-not-a-real-secret|postgres|\$\{\{.*|\$[A-Z_{]+.*)$")


def _get(path: str, token: str, raw: bool = False):
    req = urllib.request.Request(f"{_API}{path}", headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read() if raw else json.load(r)


def unmasked_assignments(log_text: str) -> int:
    """Lines assigning a secret-named variable a value that is neither masked nor a known fake."""
    text = _ANSI.sub("", log_text)
    return sum(1 for m in _ASSIGN.finditer(text) if not _KNOWN_FAKE.match(m.group(2)))


def gitleaks_count(clone_url: str, gitleaks: str) -> int:
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "clone", "-q", "--bare", clone_url, d + "/r"], check=True)
        report = d + "/report.json"
        subprocess.run([gitleaks, "git", "--redact", "--no-banner", "-f", "json", "-r", report,
                        "--exit-code", "0", d + "/r"], check=True, capture_output=True)
        with open(report, encoding="utf-8") as f:
            return len(json.load(f) or [])


def main() -> int:
    token, repo = os.environ["GITHUB_TOKEN"], os.environ["GITHUB_REPOSITORY"]
    gitleaks = os.environ.get("GITLEAKS", "gitleaks")
    owner = repo.split("/")[0]
    leaks = 0
    repos = _get(f"/users/{owner}/repos?type=public&per_page=100", token)
    others = [r for r in repos if r["full_name"] != repo and not r.get("private")]
    print(f"▶ {len(others)} autre(s) dépôt(s) public(s) de {owner}")
    for r in others:
        n = gitleaks_count(r["clone_url"], gitleaks)
        leaks += n
        print(f"   {'✗' if n else '✓'} {r['full_name']} : {n} trouvaille(s) gitleaks")
    forks = _get(f"/repos/{repo}/forks?per_page=100", token)
    print(f"▶ forks de {repo} : {len(forks)}" + (" — ils gardent l'historique" if forks else ""))
    leaks += len(forks)
    runs = _get(f"/repos/{repo}/actions/runs?per_page=30&status=completed", token)["workflow_runs"]
    hits = 0
    for run in runs:
        try:
            z = zipfile.ZipFile(io.BytesIO(_get(f"/repos/{repo}/actions/runs/{run['id']}/logs",
                                                token, raw=True)))
        except (OSError, zipfile.BadZipFile):
            continue
        n = sum(unmasked_assignments(z.read(name).decode("utf-8", "replace"))
                for name in z.namelist() if name.endswith(".txt"))
        if n:
            print(f"   ✗ run {run['id']} ({run['name']}) : {n} ligne(s) non masquée(s)")
        hits += n
    print(f"▶ journaux Actions ({len(runs)} runs) : {hits} valeur(s) non masquée(s)")
    leaks += hits
    print(f"{'❌' if leaks else '✅'} surfaces publiques : {leaks} fuite(s) potentielle(s)")
    return 1 if leaks else 0


if __name__ == "__main__":
    raise SystemExit(main())
