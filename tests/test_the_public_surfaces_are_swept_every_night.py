"""The impact sweep of a leaked secret runs every night, not when someone thinks of it.

Type: Sub
Uses: tools/dev/sweep_public_surfaces.py, .github/workflows/security-nightly.yml
Depends on: nothing — log text fabricated, no network

2026-09-25: the sibling sweep of the 12 leaked secrets (other public repos, forks, public
Actions logs) was done by hand, after the owner asked.
"""
import importlib.util
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("sps", _ROOT / "tools/dev/sweep_public_surfaces.py")
sps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sps)


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    leaked = "2026-09-25T03:00Z SPOTIFY_CLIENT_SECRET=9f8e7d6c5b4a39281706f5e4d3c2b1a0\n"  # pragma: allowlist secret  gitleaks:allow — fabricated
    assert sps.unmasked_assignments(leaked) == 1
    for masked in ("SPOTIFY_CLIENT_SECRET=***",
                   "META_APP_SECRET:  \x1b[1;33mREDACTED\x1b[0m",   # gitleaks' own output, coloured
                   "AIRFLOW_PASSWORD: ci-not-a-real-secret",
                   "POSTGRES_PASSWORD=postgres",
                   "SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}"):
        assert sps.unmasked_assignments(masked) == 0, masked


def test_the_sweep_runs_nightly_and_reaches_notify() -> None:
    wf = yaml.safe_load((_ROOT / ".github/workflows/security-nightly.yml").read_text(encoding="utf-8"))
    job = wf["jobs"]["public-surface-sweep"]
    assert "sweep_public_surfaces.py" in str(job["steps"])
    assert "public-surface-sweep" in wf["jobs"]["notify"]["needs"]
