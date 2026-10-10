"""R493 — `make night-status` names a failed nightly job the run's green verdict hides.

Type: Sub
Uses: tools/dev/night_run.py (nightly_line, _main_ci_runs)
Depends on: nothing — the verdicts are fabricated
Persists in: nothing
"""
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("night_run", _ROOT / "tools/dev/night_run.py")
nrun = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nrun)


def test_a_failed_job_under_a_green_run_is_named() -> None:
    line = nrun.nightly_line({"state": "green", "url": "u", "jobs": ["guard-mutation"]})
    assert line and "guard-mutation" in line
    assert nrun.nightly_line({"state": "green", "url": "u", "jobs": []}) is None
    assert "ILLISIBLE" in nrun.nightly_line({"state": "green", "jobs": None})
    assert "ILLISIBLE" in nrun.nightly_line(None)
    assert "ROUGE" in nrun.nightly_line({"state": "red", "since": "2026-10-09"})


def test_mains_ci_verdict_reads_the_ci_workflow_only(monkeypatch) -> None:
    """A scheduled nightly runs on main too: unfiltered, its green run broke a red CI streak."""
    seen = []

    def fake_run(argv, **_):
        seen.append(argv)
        raise OSError("no gh here")
    monkeypatch.setattr(nrun.subprocess, "run", fake_run)
    assert nrun._main_ci_runs() is None
    argv = seen[0]
    assert argv[argv.index("--workflow") + 1] == "ci.yml"
