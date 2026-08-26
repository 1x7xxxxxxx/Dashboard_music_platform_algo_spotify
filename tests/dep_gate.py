"""One place that answers "is this runtime dependency really importable here?".

Sibling of `db_gate`, written for the same measured reason and with the same shape.

Measured 2026-08-26: `python3 -m pytest tests/` reported **32 failures** on a clean
tree. Twenty-eight were `ImportError: cannot import name 'DAG' from 'airflow'` and
`ModuleNotFoundError: No module named 'googleapiclient'` — the suite was simply being
run by an interpreter that does not have them (`/usr/bin/python3`, not the project
environment). Four CI-blocking error classes reported HIT for the same reason.

Thirty-two red tests that mean "wrong interpreter" is the same disease as an alert
that fires every night for a working pipeline: the reader learns to skip the summary,
and a real failure arrives dressed identically.

The `airflow` case has a trap worth naming, because it makes the diagnosis look like
a broken package. This repo has a top-level `airflow/` DIRECTORY. Run from the repo
root, `''` is on `sys.path`, so `import airflow` binds to that directory as a
NAMESPACE package — `airflow.__path__` is a `_NamespacePath` and `from airflow import
DAG` fails with "unknown location", which reads as a corrupt install rather than an
absent one. So the probe checks for the real package, not merely for importability.

**The pairing that makes skipping safe.** A gate that turns failures into skips can
hide a genuine breakage, so it must be impossible for CI to take that path:
`test_ci_never_skips_a_dependency_gate` asserts that when `CI` is set, every gated
dependency is present. Skipping is a courtesy to a developer's shell, never a
behaviour of the pipeline.
"""
from __future__ import annotations

import importlib.util
import os

import pytest

# name -> (import name, what to run to get it)
GATED = {
    "airflow": ("airflow", "uv sync --frozen --extra dev  (or: make sync)"),
    "googleapiclient": ("googleapiclient", "uv sync --frozen  (google-api-python-client)"),
    "spotipy": ("spotipy", "uv sync --frozen  (spotipy)"),
}


def _really_importable(module: str) -> bool:
    """True only for a REAL package — a namespace portion does not count.

    `airflow/` at the repo root is picked up as a namespace package whenever the
    suite runs from the repo root, so `find_spec` alone answers "yes" for a
    dependency that is not installed at all.
    """
    try:
        spec = importlib.util.find_spec(module)
    except (ImportError, ValueError):
        return False
    return spec is not None and spec.origin is not None


def missing() -> list[str]:
    """The gated dependencies this interpreter does not actually have."""
    return sorted(n for n, (mod, _) in GATED.items() if not _really_importable(mod))


def skip_reason(name: str) -> str:
    mod, how = GATED[name]
    return (f"`{mod}` is not installed for this interpreter — this suite cannot "
            f"prove anything about it here. Install it with: {how}")


def requires(name: str):
    """`pytestmark = requires('airflow')` at the top of a module."""
    if name not in GATED:
        raise KeyError(f"unknown gated dependency {name!r}; known: {sorted(GATED)}")
    return pytest.mark.skipif(
        not _really_importable(GATED[name][0]), reason=skip_reason(name))


def is_ci() -> bool:
    return str(os.environ.get("CI", "")).strip().lower() in {"1", "true", "yes"}
