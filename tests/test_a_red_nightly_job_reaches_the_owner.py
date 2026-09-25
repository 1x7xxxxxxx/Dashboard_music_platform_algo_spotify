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
    # As GitHub really reports it: `success` under continue-on-error, the truth in outputs.
    "gitleaks": {"result": "success", "outputs": {"outcome": "failure"}},
    "full-suite-random-order": {"result": "success", "outputs": {}},
}


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    body = nv.verdict(_NIGHT_OF_09_25)
    assert body and "gitleaks" in body and "runbook §27" in body
    assert "3 avis" in body and "7 HIT" in body, "the swallowed counters ride in the body"


def test_a_clean_night_sends_nothing_even_with_advisories() -> None:
    clean = {k: {"result": "success", "outputs": {**v["outputs"], "outcome": "success"}}
             for k, v in _NIGHT_OF_09_25.items()}
    assert nv.verdict(clean) is None, "counters alone must not mail every night"


def test_the_workflow_wires_the_notify_job_to_every_job() -> None:
    wf = yaml.safe_load((_ROOT / ".github/workflows/security-nightly.yml").read_text(encoding="utf-8"))
    jobs = wf["jobs"]
    notify = jobs["notify"]
    assert set(notify["needs"]) == set(jobs) - {"notify"}, "a job left out of `needs` fails in silence"
    assert "always()" in str(notify["if"])
    assert jobs["pip-audit"].get("outputs", {}).get("vulns")
    assert jobs["error-class-audit"].get("outputs", {}).get("hits")
    assert jobs["gitleaks"].get("outputs", {}).get("outcome"), "needs.result lies under continue-on-error"
    assert jobs["full-suite-random-order"].get("outputs", {}).get("outcome")


def _uses_a_form_the_ci_gitleaks_ignores(toml_text: str) -> bool:
    """The CI action embeds gitleaks 8.24.3, which silently ignores `[[allowlists]]` (8.25+)."""
    import tomllib
    return "allowlists" in tomllib.loads(toml_text)


def test_the_gitleaks_allowlist_is_read_by_the_ci_version() -> None:
    """Measured 2026-09-25: the plural form gave 12 findings locally (8.28), 24 in CI (8.24.3)."""
    assert not _uses_a_form_the_ci_gitleaks_ignores((_ROOT / ".gitleaks.toml").read_text(encoding="utf-8"))
    assert _uses_a_form_the_ci_gitleaks_ignores("[[allowlists]]\npaths = ['x']\n")
    assert not _uses_a_form_the_ci_gitleaks_ignores("[allowlist]\npaths = ['x']\n")


def test_a_reopening_condition_reaches_the_owner_every_night() -> None:
    """R170: `reopen-check` had no scheduled caller; on the day it was wired, R122's condition
    had been met since the morning, seen by nobody."""
    wf = yaml.safe_load((_ROOT / ".github/workflows/security-nightly.yml").read_text(encoding="utf-8"))
    job = wf["jobs"]["reopen-check"]
    assert "reopen_check.py" in str(job["steps"]) and job.get("outputs", {}).get("outcome")
    body = nv.verdict({"reopen-check": {"result": "success", "outputs": {"outcome": "failure"}}})
    assert body and "réouverture" in body


# ── Structural half (2026-09-25, second pass) ──────────────────────────────────────────
# The first pass wired `outcome` on three jobs and left three dark: pip-audit, the error-class
# audit and action-drift reported `success` whatever happened, and `reopen-check` — wired the
# same day — piped its verdict through `tee` without pipefail, so its `exit 1` became 0.
_WORKFLOWS = sorted((_ROOT / ".github/workflows").glob("*.yml"))


def _pipe_without_pipefail(step: dict, job: dict, wf: dict) -> bool:
    """A `run:` with a pipe whose shell does not propagate the left side's failure.

    GitHub's DEFAULT shell is `bash -e {0}` (no pipefail); an EXPLICIT `shell: bash` is
    `bash -eo pipefail {0}`."""
    run = step.get("run") or ""
    if not any("|" in ln.replace("||", "") for ln in run.splitlines()):
        return False
    shell = (step.get("shell") or (job.get("defaults") or {}).get("run", {}).get("shell")
             or (wf.get("defaults") or {}).get("run", {}).get("shell"))
    return shell != "bash" and "set -o pipefail" not in run


def _dark_jobs(wf: dict) -> list[str]:
    """Jobs under `continue-on-error` whose real outcome never reaches `notify`."""
    out = []
    for name, job in (wf.get("jobs") or {}).items():
        if name == "notify" or not job.get("continue-on-error"):
            continue
        ids = {s.get("id") for s in job.get("steps", [])}
        o = str((job.get("outputs") or {}).get("outcome", ""))
        if not any(f"steps.{i}.outcome" in o for i in ids if i):
            out.append(name)
    return out


def test_every_nightly_job_publishes_its_real_outcome() -> None:
    wf = yaml.safe_load((_ROOT / ".github/workflows/security-nightly.yml").read_text(encoding="utf-8"))
    assert _dark_jobs(wf) == [], "these jobs can fail and still read `success` to notify"


def test_no_workflow_pipes_a_verdict_through_a_shell_without_pipefail() -> None:
    bad = []
    for path in _WORKFLOWS:
        wf = yaml.safe_load(path.read_text(encoding="utf-8"))
        for jn, job in (wf.get("jobs") or {}).items():
            for st in job.get("steps", []):
                if _pipe_without_pipefail(st, job, wf):
                    bad.append(f"{path.name}:{jn}:{st.get('name') or st.get('id')}")
    assert bad == [], f"a pipe hides the command's exit code: {bad}"


def test_a_step_skipped_behind_a_failed_one_mails() -> None:
    body = nv.verdict({"full-suite-random-order": {"result": "success",
                                                   "outputs": {"outcome": "skipped"}}})
    assert body and "full-suite-random-order" in body


def test_the_structural_detectors_see_the_defects_they_are_written_for() -> None:
    """Non-vacuity: the exact shapes of 2026-09-25, and their corrected forms."""
    tee = {"id": "r", "run": 'python3 tools/dev/reopen_check.py | tee -a "$GITHUB_STEP_SUMMARY"'}
    assert _pipe_without_pipefail(tee, {}, {})
    assert not _pipe_without_pipefail({**tee, "shell": "bash"}, {}, {})
    assert not _pipe_without_pipefail({**tee, "run": "set -o pipefail\n" + tee["run"]}, {}, {})
    assert not _pipe_without_pipefail({"run": "make x || true"}, {}, {}), "`||` is not a pipe"
    dark = {"jobs": {"pip-audit": {"continue-on-error": True, "outputs": {"vulns": "x"},
                                   "steps": [{"id": "count", "run": "x"}]}}}
    assert _dark_jobs(dark) == ["pip-audit"]
    dark["jobs"]["pip-audit"]["outputs"]["outcome"] = "${{ steps.count.outcome }}"
    assert _dark_jobs(dark) == []
