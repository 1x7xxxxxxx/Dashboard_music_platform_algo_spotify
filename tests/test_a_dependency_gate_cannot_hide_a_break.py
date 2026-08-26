"""Turning red into skipped is only safe if CI can never take that path.

Measured 2026-08-26: `python3 -m pytest tests/` reported 32 failures on a clean tree,
28 of them `ImportError: cannot import name 'DAG' from 'airflow'` and
`ModuleNotFoundError: No module named 'googleapiclient' / 'spotipy'`. The suite was
run by an interpreter without the project's dependencies. Four CI-blocking error
classes reported HIT for that reason alone.

Thirty-two red tests that mean "wrong interpreter" is the same disease as a nightly
alert that fires for a working pipeline: the reader stops reading, and a real failure
arrives dressed identically. So they skip — but a skip is the more dangerous half of
the trade, and this repo has already paid for it once: four waves of tenant-isolation
work shipped against "163 skipped" reading as green (`tests/conftest.py`).

Two things make it safe, and both are asserted here rather than assumed:

  * the terminal summary SHOUTS which dependency is absent and what to run;
  * `CI` present ⇒ nothing may be gated away. The pipeline proves, or it fails.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from tests.dep_gate import GATED, _really_importable, is_ci, missing

REPO = pathlib.Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not is_ci(), reason="only meaningful inside CI")
def test_ci_never_skips_a_dependency_gate():
    """THE assertion. Without it, a broken CI image turns every DAG test into a
    silent skip and the pipeline reports success on nothing."""
    absent = missing()
    assert not absent, (
        f"CI is missing {absent}. In CI these gates must never fire: skipping is a "
        "courtesy to a developer's shell, never a behaviour of the pipeline.")


def test_the_gate_tells_a_namespace_directory_from_a_real_package():
    """`airflow/` at the repo root is captured as a namespace package, so
    `find_spec('airflow')` answers yes for a dependency that is not installed —
    and `from airflow import DAG` then fails with 'unknown location', which reads
    as a corrupt install rather than an absent one."""
    import importlib.util

    spec = importlib.util.find_spec("airflow")
    if spec is not None and spec.origin is None:
        assert not _really_importable("airflow"), (
            "the probe accepted a namespace portion as an installed package — the "
            "exact confusion this gate exists to remove")
    assert _really_importable("pathlib"), "the probe rejects a genuinely real package"


def test_every_gated_dependency_names_the_command_that_installs_it():
    """A refusal that does not say what to run is a dead end (same contract as the
    non-production mail gate)."""
    for name, (mod, how) in GATED.items():
        assert how and ("sync" in how or "pip" in how), (
            f"{name} is gated with no actionable install command: {how!r}")


def test_the_summary_shouts_rather_than_scrolls():
    conftest = (REPO / "tests/conftest.py").read_text(encoding="utf-8")
    assert "DÉPENDANCES ABSENTES" in conftest
    assert "red=True" in conftest, "a quiet notice is what 163 skipped already was"


def test_no_module_assigns_pytestmark_twice():
    """A second `pytestmark = …` silently discards the first.

    Found in `test_e2e_two_tenants.py` while installing these gates: the module had
    `pytestmark = requires("airflow")` and, sixty lines lower,
    `pytestmark = requires_live_db()`. The second won, the first vanished, and the
    module looked gated while running ungated. Conditions must go in one list.
    """
    offenders = []
    for f in sorted((REPO / "tests").glob("test_*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        n = sum(1 for node in tree.body
                if isinstance(node, ast.Assign)
                and any(getattr(t, "id", "") == "pytestmark" for t in node.targets))
        if n > 1:
            offenders.append(f"{f.name} ({n} assignments)")
    assert not offenders, (
        "a module assigns `pytestmark` more than once; the last wins and every "
        f"earlier gate is silently dropped — use one list instead: {offenders}")
