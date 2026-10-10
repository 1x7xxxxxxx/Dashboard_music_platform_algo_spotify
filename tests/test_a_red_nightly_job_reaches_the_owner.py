"""A failed job of the nightly security workflow mails the owner — even one allowed to fail.

Type: Sub
Uses: tools/dev/nightly_verdict.py, .github/workflows/security-nightly.yml
Depends on: nothing — fabricated `needs` context, nothing is sent

Measured 2026-09-25: `gitleaks` red 5 nights out of 5, the random-order suite 4 out of 5,
under a workflow that `continue-on-error` kept green and nobody read.
"""
import importlib.util
import re
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


# ── R495: the PROPERTY, not the form ─────────────────────────────────────────────────────
# `_dark_jobs` used to ask « does `outputs.outcome` reference at least one step? ». That is a
# form: `guard-mutation` referenced `mutate` and the upload step after it (`if: always()`)
# could fail unseen. The guard now SIMULATES each step failing, evaluates the real
# `outputs.outcome` expression on the resulting step outcomes, and requires a failure value.
_TOKEN = re.compile(r"\s*(?:(?P<str>'(?:[^']|'')*')|(?P<op>&&|\|\||==|!=|!|\(|\))"
                    r"|(?P<ref>[A-Za-z_][\w.-]*))")


def evaluate(expr: str, outcomes: dict[str, str]) -> object:
    """Evaluate a GitHub `${{ }}` expression over `steps.<id>.outcome` — `&&`/`||` return an
    operand, as GitHub does. Anything else (another context, a function) raises."""
    body = re.fullmatch(r"\s*\$\{\{(.*)\}\}\s*", expr, re.S)
    if not body:
        raise ValueError(f"not a single expression: {expr!r}")
    text, toks, pos = body.group(1), [], 0
    while text[pos:].strip():
        m = _TOKEN.match(text, pos)
        if not m:
            raise ValueError(f"cannot read {text[pos:]!r}")
        toks.append(m.group("str") or m.group("op") or m.group("ref"))
        pos = m.end()
    val, rest = _or(toks, outcomes)
    if rest:
        raise ValueError(f"trailing tokens {rest}")
    return val


def _or(t: list, o: dict) -> tuple:
    left, t = _and(t, o)
    while t[:1] == ["||"]:
        right, t = _and(t[1:], o)
        left = left or right
    return left, t


def _and(t: list, o: dict) -> tuple:
    left, t = _cmp(t, o)
    while t[:1] == ["&&"]:
        right, t = _cmp(t[1:], o)
        left = left and right
    return left, t


def _cmp(t: list, o: dict) -> tuple:
    left, t = _unary(t, o)
    if t[:1] in (["=="], ["!="]):
        op, (right, t) = t[0], _unary(t[1:], o)
        same = str(left).lower() == str(right).lower()
        return (same if op == "==" else not same), t
    return left, t


def _unary(t: list, o: dict) -> tuple:
    if t[:1] == ["!"]:
        v, t = _unary(t[1:], o)
        return (not v), t
    if t[:1] == ["("]:
        v, t = _or(t[1:], o)
        if t[:1] != [")"]:
            raise ValueError("unbalanced parenthesis")
        return v, t[1:]
    tok, t = t[0], t[1:]
    if tok.startswith("'"):
        return tok[1:-1].replace("''", "'"), t
    if tok in ("true", "false"):
        return tok == "true", t
    m = re.fullmatch(r"steps\.([\w-]+)\.outcome", tok)
    if not m:
        raise ValueError(f"unknown reference {tok!r}")
    return o.get(m.group(1), ""), t


def _runs(step: dict, job_failed: bool) -> bool:
    cond = str(step.get("if") or "")
    if "always()" in cond:
        return True
    if "failure()" in cond:
        return job_failed
    return not job_failed          # the implicit `success()`


def outcomes_when(steps: list[dict], failing: int) -> dict[str, str]:
    """Every step id's outcome when step #`failing` fails and every other step that runs succeeds."""
    out, job_failed = {}, False
    for i, st in enumerate(steps):
        if i == failing:
            state = "failure"
            job_failed = job_failed or not st.get("continue-on-error")
        else:
            state = "success" if _runs(st, job_failed) else "skipped"
        if st.get("id"):
            out[st["id"]] = state
    return out


def _dark_jobs(wf: dict) -> list[str]:
    """Jobs whose real outcome can fail to reach `notify`.

    A job under `continue-on-error` must publish `outputs.outcome`; any job that publishes
    one (it WINS over `needs.<job>.result` in nightly_verdict) must render a failure value for
    every single step that fails, and `success` on a clean night."""
    out = []
    for name, job in (wf.get("jobs") or {}).items():
        if name == "notify":
            continue
        expr = (job.get("outputs") or {}).get("outcome")
        if not expr:
            if job.get("continue-on-error"):
                out.append(name)
            continue
        steps = job.get("steps") or []
        failing = [evaluate(str(expr), outcomes_when(steps, i)) for i in range(len(steps))]
        clean = evaluate(str(expr), outcomes_when(steps, -1))
        if clean != "success" or any(v not in nv._FAILED for v in failing):
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
    # R495 — the exact 2026-10-10 shape: the referenced step first, an unreferenced
    # `if: always()` upload after it. Its failure skips nothing, so nothing reads it.
    upload = {"name": "Keep the dated reds", "if": "always()", "uses": "actions/upload-artifact@v4"}
    shape = {"jobs": {"guard-mutation": {
        "continue-on-error": True, "outputs": {"outcome": "${{ steps.mutate.outcome }}"},
        "steps": [{"uses": "actions/checkout@v6"},
                  {"id": "mutate", "continue-on-error": True, "run": "x"}, upload]}}}
    assert _dark_jobs(shape) == ["guard-mutation"]
    job = shape["jobs"]["guard-mutation"]
    job["steps"][2] = {**upload, "id": "keep"}
    assert _dark_jobs(shape) == ["guard-mutation"], "an id nobody reads covers nothing"
    job["outputs"]["outcome"] = ("${{ steps.mutate.outcome != 'success' && steps.mutate.outcome"
                                 " || steps.keep.outcome }}")
    assert _dark_jobs(shape) == []
    # The id string PRESENT but off the evaluation path — a text match would pass it.
    job["outputs"]["outcome"] = ("${{ steps.keep.outcome == 'never' && steps.keep.outcome"
                                 " || steps.mutate.outcome }}")
    assert _dark_jobs(shape) == ["guard-mutation"]
    # An outcome that reads failure every night would mail every night: flagged too.
    job["outputs"]["outcome"] = "${{ 'failure' }}"
    assert _dark_jobs(shape) == ["guard-mutation"]


def test_the_expression_reader_follows_github_semantics() -> None:
    """`&&`/`||` return an OPERAND (not a bool), and `==` compares case-insensitively."""
    chain = "${{ steps.a.outcome != 'success' && steps.a.outcome || steps.b.outcome }}"
    assert evaluate(chain, {"a": "skipped", "b": "success"}) == "skipped"
    assert evaluate(chain, {"a": "success", "b": "failure"}) == "failure"
    assert evaluate("${{ steps.a.outcome == 'SUCCESS' }}", {"a": "success"}) is True
    assert evaluate("${{ !(steps.a.outcome == 'x') }}", {"a": "y"}) is True
    try:
        evaluate("${{ github.ref }}", {})
    except ValueError:
        pass
    else:
        raise AssertionError("an unknown context must raise, never read as empty")


def test_a_blocking_advisory_reaches_notify() -> None:
    """R493: `outcome` read the `count` step only; the two gates after it could fail and
    the job still told notify « success »."""
    wf = yaml.safe_load((_ROOT / ".github/workflows/security-nightly.yml").read_text(encoding="utf-8"))
    job = wf["jobs"]["pip-audit"]
    ids = {s.get("id") for s in job["steps"]}
    outcome = job["outputs"]["outcome"]
    for step in ("count", "gate", "gate_api"):
        assert step in ids and f"steps.{step}.outcome" in outcome, step


def test_a_lost_upload_of_the_dated_reds_reaches_notify() -> None:
    """R495: the REAL `outputs.outcome` of guard-mutation, evaluated with `mutate` green and
    `keep` red, handed to the real nightly_verdict — no hand-written outputs dict."""
    wf = yaml.safe_load((_ROOT / ".github/workflows/security-nightly.yml").read_text(encoding="utf-8"))
    job = wf["jobs"]["guard-mutation"]
    assert "keep" in {s.get("id") for s in job["steps"]}
    value = evaluate(job["outputs"]["outcome"], {"mutate": "success", "keep": "failure"})
    needs = {"guard-mutation": {"result": "success", "outputs": {"outcome": value}}}
    assert nv.failed_jobs(needs) == ["guard-mutation"]
    assert "guard-mutation" in (nv.annotation(nv.failed_jobs(needs)) or "")
    assert "Keep the dated reds" in (nv.verdict(needs) or ""), "the mail must name the step"
