"""Guard: a blocking gate may fail the build; it may not make the rest invisible.

Type: Utility
Uses: yaml, pathlib
Triggers: pytest
Persists in: nothing

Error class `red-gate-hides-every-step-behind-it`.

Measured 2026-09-06 with `gh run list`. `.github/workflows/ci.yml` runs the
error-class guards at step 10 of 15. A step failure skips every later step by
default, so `Run tests` — the suite, 3700+ tests, the only thing in this workflow
that can say the product still works — did not execute for **27 consecutive runs**
between 2026-09-04T22:36 and 2026-09-06T07:19. Twenty-seven commits reached `main`
on a single red signal that was always the same two guards, and nothing behind it.

The cause of those two guards' red had nothing to do with the suite: they read
`META_BUSINESS_ID` from the operator's `.env` (see
`guard-predicate-depends-on-the-host-env`). That is the shape of the class — the
gate that fails is rarely the thing you most need to see.

What this asserts is narrow on purpose: every step AFTER the first blocking gate
must declare a condition that survives an earlier failure. It does not ask the gate
to stop blocking — a red guard still fails the job. It asks that the job keep
reporting.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


CI = _repo_root() / ".github" / "workflows" / "ci.yml"

# The gates that are allowed to hide what follows them. Installing dependencies is
# one: nothing after it can run at all, so letting later steps try buys a wall of
# identical noise instead of a report. Everything after the LAST of these must
# survive an earlier failure.
_SETUP_STEPS = (
    "Install uv",
    "Set up Python 3.11",
    "Install system dependencies (build tools for any wheel-less package)",
    "Install dependencies from lockfile",
)

_SURVIVES = ("!cancelled()", "always()", "success() || failure()")


def _steps() -> list[dict]:
    doc = yaml.safe_load(CI.read_text(encoding="utf-8"))
    return doc["jobs"]["lint-and-test"]["steps"]


def test_the_suite_step_still_runs_when_an_earlier_gate_fails():
    """The 27-run outage, asked as one question."""
    steps = _steps()
    run_tests = [s for s in steps if s.get("name") == "Run tests"]
    assert run_tests, "ci.yml no longer has a step named 'Run tests'"
    cond = str(run_tests[0].get("if", ""))
    assert any(tok in cond for tok in _SURVIVES), (
        "`Run tests` is skipped whenever any earlier step fails. That is how the "
        "suite stopped running for 27 consecutive CI runs on 2026-09-04..06 while "
        "every one of them reported a failure — of something else. Give it "
        "`if: ${{ !cancelled() }}`; the job still fails on the gate."
    )


def test_every_step_after_setup_reports_rather_than_disappears():
    """One skipped step is a gap in the report, not just a saved minute."""
    steps = _steps()
    names = [s.get("name") for s in steps]
    last_setup = max(names.index(n) for n in _SETUP_STEPS if n in names)
    hidden = [
        s.get("name") for s in steps[last_setup + 1:]
        if not any(tok in str(s.get("if", "")) for tok in _SURVIVES)
        and s.get("name") not in ("Manifest consistency (blocking)",
                                  "Lint (ruff) — full project (blocking)",
                                  "REX integrity + deterministic error-class guards "
                                  "(blocking)")
    ]
    assert not hidden, (
        f"{hidden} vanish from the report as soon as anything before them fails. "
        "The three blocking gates are exempt — they are what may legitimately stop "
        "the build — but nothing after them should go unreported."
    )
