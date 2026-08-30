"""`make test` and CI must distribute the suite the same way.

Type: Test
Uses: re
Depends on: Makefile, .github/workflows/ci.yml
Persists in: nothing

Why this is worth a test
------------------------
Until 2026-08-30 CI ran `pytest -n auto --dist loadfile` and `make test` ran a plain
serial `pytest`. Two consequences, and the second is the expensive one:

* the local suite took 238 s where the same machine needed 151 s (measured);
* "green locally" and "green in CI" were not the same claim. This repo has already
  paid for that once: a caching defect stayed green in every local run and failed only
  on the runner.

`--dist loadfile` is not decoration. It keeps a file's tests on one worker, which is
what any test carrying module-level state depends on; plain `-n auto` scatters them and
turns such a test into a coin flip.

What this asserts
-----------------
Only that the two agree on the distribution flags. It does not pin the value: raising
or lowering parallelism is a legitimate decision — making it in ONE of the two places
is not.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_MAKEFILE = _ROOT / "Makefile"
_CI = _ROOT / ".github/workflows/ci.yml"

_FLAGS = re.compile(r"(-n\s+\S+|--dist\s+\S+)")


def _ci_pytest_line() -> str:
    for line in _CI.read_text(encoding="utf-8").splitlines():
        if "pytest tests/" in line:
            return line
    raise AssertionError(
        "no `pytest tests/` invocation found in ci.yml — if CI stopped running the "
        "suite, that is the finding, not this test's bookkeeping."
    )


def _makefile_pytest_flags() -> set[str]:
    body = _MAKEFILE.read_text(encoding="utf-8")
    m = re.search(r"^PYTEST_DIST\s*:?=\s*(.+)$", body, re.M)
    assert m, (
        "the Makefile no longer defines PYTEST_DIST. It exists so the local suite and "
        "CI cannot drift apart silently."
    )
    return set(_FLAGS.findall(m.group(1)))


def test_the_local_target_uses_the_pytest_dist_variable():
    body = _MAKEFILE.read_text(encoding="utf-8")
    m = re.search(r"^test:.*?\n((?:\t.*\n)+)", body, re.M)
    assert m, "the Makefile has no `test:` target any more"
    assert "$(PYTEST_DIST)" in m.group(1), (
        "`make test` no longer passes $(PYTEST_DIST), so it can run the suite "
        "differently from CI without anything saying so."
    )


def test_the_two_agree_on_how_the_suite_is_distributed():
    ci = set(_FLAGS.findall(_ci_pytest_line()))
    local = _makefile_pytest_flags()
    assert ci == local, (
        f"CI distributes the suite with {sorted(ci)} and `make test` with {sorted(local)}.\n"
        "Green locally and green in CI then mean different things — this repo already "
        "shipped a defect that only the runner could see.\n"
        "Change both, or neither."
    )
