"""A failed job of the nightly security workflow mails the owner — the workflow stays green.

Type: Sub
Uses: tools/dev/nightly_verdict.py, .github/workflows/security-nightly.yml
Depends on: nothing — fabricated `needs` context, nothing is sent

Measured 2026-09-25: `gitleaks` red 5 nights out of 5, the random-order suite 4 out of 5,
under a workflow that `continue-on-error` kept green and nobody read.
"""
import importlib.util
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("nightly_verdict", _ROOT / "tools/dev/nightly_verdict.py")
nv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nv)

_NIGHT_OF_09_25 = {
    "pip-audit": {"result": "success", "outputs": {"vulns": "3"}},
    "error-class-audit": {"result": "success", "outputs": {"hits": "7"}},
    "action-drift": {"result": "success", "outputs": {}},
    "gitleaks": {"result": "failure", "outputs": {}},
    "full-suite-random-order": {"result": "success", "outputs": {}},
}


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    body = nv.verdict(_NIGHT_OF_09_25)
    assert body and "gitleaks" in body and "runbook §27" in body
    assert "3 avis" in body and "7 HIT" in body, "the swallowed counters ride in the body"


def test_a_clean_night_sends_nothing_even_with_advisories() -> None:
    clean = {k: {**v, "result": "success"} for k, v in _NIGHT_OF_09_25.items()}
    assert nv.verdict(clean) is None, "counters alone must not mail every night"


def test_the_workflow_wires_the_notify_job_to_every_job() -> None:
    wf = yaml.safe_load((_ROOT / ".github/workflows/security-nightly.yml").read_text(encoding="utf-8"))
    jobs = wf["jobs"]
    notify = jobs["notify"]
    assert set(notify["needs"]) == set(jobs) - {"notify"}, "a job left out of `needs` fails in silence"
    assert "always()" in str(notify["if"])
    assert jobs["pip-audit"].get("outputs", {}).get("vulns")
    assert jobs["error-class-audit"].get("outputs", {}).get("hits")
