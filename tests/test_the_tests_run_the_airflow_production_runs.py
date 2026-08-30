"""The Airflow the tests import must be the Airflow production executes.

Type: Test
Uses: tomllib-free line parsing of uv.lock, re
Depends on: uv.lock, Dockerfile.airflow
Persists in: nothing

The defect
----------
Measured 2026-08-30:

    Dockerfile.airflow   ARG AIRFLOW_VERSION=2.11.2   (and apache/airflow:2.11.2)
    uv.lock              apache-airflow  3.2.2
    production           2.11.2

Nothing in this repo pins Airflow for the DEV environment. `requirements.txt` lists
`apache-airflow-providers-*` with no version, and the resolver is free to bring a
core along with them — which it did, a major version ahead of production.

`Dockerfile.airflow` already knows this and defends the IMAGE with a one-line
`--constraint`; its comment says so at length. What it cannot defend is the
interpreter the tests run in. So every DAG-shaped test that does run validates the
DAGs against an Airflow production does not execute, and reports green.

This is not hypothetical here: Dependabot PR #100 proposed Airflow 3.3.0 and would
have broken the import of all 16 DAGs. The image's constraint would have caught it
at build time — after the suite had already gone green.

What this asserts
-----------------
That the two declarations agree on the MAJOR version. Patch drift between a lock
file and an image tag is ordinary; a major is the thing that moved `schedule_interval`
and `provide_context` out from under the DAGs.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_LOCK = _ROOT / "uv.lock"
_DOCKERFILE = _ROOT / "Dockerfile.airflow"


def dockerfile_airflow_version() -> str:
    # utf-8-sig: Dockerfile.airflow carries a UTF-8 BOM, which makes a bare
    # `^FROM` fail to match on line 1. Docker tolerates the BOM; a reader must too.
    body = _DOCKERFILE.read_text(encoding="utf-8-sig")
    m = re.search(r"^ARG\s+AIRFLOW_VERSION=([0-9][0-9A-Za-z.\-]*)", body, re.M)
    assert m, "Dockerfile.airflow no longer declares ARG AIRFLOW_VERSION"
    return m.group(1)


def dockerfile_base_image_version() -> str:
    # utf-8-sig: Dockerfile.airflow carries a UTF-8 BOM, which makes a bare
    # `^FROM` fail to match on line 1. Docker tolerates the BOM; a reader must too.
    body = _DOCKERFILE.read_text(encoding="utf-8-sig")
    m = re.search(r"^FROM\s+apache/airflow:([0-9][0-9A-Za-z.]*)", body, re.M)
    assert m, "Dockerfile.airflow no longer starts FROM apache/airflow:<version>"
    return m.group(1)


def lock_airflow_version() -> str | None:
    """The apache-airflow version uv.lock resolves, or None if it holds none."""
    lines = _LOCK.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.strip() == 'name = "apache-airflow"':
            for nxt in lines[i + 1:i + 4]:
                m = re.match(r'\s*version = "([^"]+)"', nxt)
                if m:
                    return m.group(1)
    return None


def _major(v: str) -> int:
    return int(v.split(".")[0])


def test_the_image_tag_and_the_build_arg_agree():
    """The two places the image names its own Airflow must not drift apart."""
    assert dockerfile_base_image_version() == dockerfile_airflow_version(), (
        f"Dockerfile.airflow builds FROM apache/airflow:{dockerfile_base_image_version()} "
        f"but constrains the core to {dockerfile_airflow_version()}. One of them is a typo, "
        "and the constraint exists precisely so that mismatch fails loudly."
    )


def test_the_lock_does_not_carry_a_different_airflow_major_than_production():
    locked = lock_airflow_version()
    if locked is None:
        pytest.skip("uv.lock resolves no apache-airflow core — nothing to compare")
    prod = dockerfile_airflow_version()
    assert _major(locked) == _major(prod), (
        f"uv.lock resolves apache-airflow {locked}; production runs {prod}.\n"
        f"Every DAG-shaped test in this suite therefore validates the DAGs against an "
        f"Airflow that production does not execute, and reports green.\n"
        f"Pin the core in pyproject.toml (the providers pull it transitively and the "
        f"resolver is free to move it), then `uv lock`. Dockerfile.airflow already "
        f"defends the IMAGE with --constraint; this defends the interpreter."
    )


def test_the_interpreter_running_this_suite_matches_production():
    """The load-bearing one: what will `import airflow` actually give a test here?"""
    # `find_spec` alone is not enough, and the way it fails here is instructive: this
    # repo has an `airflow/` DIRECTORY at its root, and the root is on sys.path, so
    # `find_spec("airflow")` returns a namespace package with `origin is None` even
    # when the real distribution is absent. Asking for `.__version__` on that raises
    # AttributeError instead of skipping. A spec with no origin is not a module.
    spec = importlib.util.find_spec("airflow")
    if spec is None or spec.origin is None:
        pytest.skip("airflow is not importable in this interpreter (or resolves to "
                    "this repo's own airflow/ directory) — the DAG tests skip too, "
                    "so there is no wrong version to run against")
    import airflow
    prod = dockerfile_airflow_version()
    assert _major(airflow.__version__) == _major(prod), (
        f"This interpreter imports airflow {airflow.__version__}; production runs {prod}. "
        "A DAG that imports here proves nothing about the scheduler that will load it."
    )
