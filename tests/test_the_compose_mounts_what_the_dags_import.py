"""A check that cannot import its own script alarms about the mount, not the data.

Measured 2026-08-26 on a real alert mail. Two sections reported the same thing:

    🐤 Le canari ne passe plus le préflight — ALL: check could not run:
       ModuleNotFoundError: No module named 'tools'
    🧬 Contamination locataire — UNAVAILABLE: check could not run:
       ModuleNotFoundError: No module named 'tools'

and both reached the SUBJECT LINE as `🐤 PRÉFLIGHT ROUGE` and `🧬 CONTAMINATION : 1`.
Answering "I could not run" is correct for those checks — a check that cannot run must
never look like one that passed. The defect was upstream, and NOT where it first
looked: the tracked template `docker-compose.example.yml` mounts `./tools:ro` into all
three Airflow services, and so does production. It was the **local, untracked**
`docker-compose.yml` — hand-derived from the template, gitignored, and therefore
invisible to every existing guard — that had drifted.

That is `prod-compose-drift` pointed the other way: not "prod drifted from the repo"
but "a working copy drifted from the template". The alarm then fires only OFF
production, which is exactly where nobody chases it.

So the guard asserts the TEMPLATE (tracked, present in CI) and additionally the local
copy WHEN it exists — never failing CI for a file CI does not have, and never letting
a developer's silently-drifted copy pass unmentioned.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "docker-compose.example.yml"
LOCAL = REPO / "docker-compose.yml"          # gitignored; absent in CI

_DAG_SERVICES = ("airflow-init", "airflow-webserver", "airflow-scheduler")
_MOUNT = re.compile(r"-\s+\./([A-Za-z0-9_./-]+):/opt/airflow/([A-Za-z0-9_-]+)")


def _mounts(path: pathlib.Path) -> list[tuple[str, str]]:
    return _MOUNT.findall(path.read_text(encoding="utf-8"))


def _top_level_imports(path: pathlib.Path) -> set:
    out = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module.split(".")[0])
    return out


# Supplied by the runtime image, never mounted from the repo — stated, not derived.
#
# `airflow` is the trap that makes this list necessary and it is worth naming: the
# repo HAS a top-level `airflow/` directory, so "is there a directory of that name?"
# answers yes for a package that comes from the image. That directory holds `dags/`,
# mounted at a different target (`/opt/airflow/dags`). It is the same confusion
# `tests/dep_gate.py` removes on the import side, where the directory is captured as
# a namespace package and an ABSENT dependency looks like a CORRUPT one.
_RUNTIME_PROVIDED = {"airflow"}


def _packages_the_dags_import() -> set:
    """Repo-local top-level packages imported by a DAG, that a container must mount."""
    wanted = set()
    for dag in (REPO / "airflow/dags").glob("*.py"):
        wanted |= _top_level_imports(dag)
    return {p for p in wanted if (REPO / p).is_dir()} - _RUNTIME_PROVIDED


def test_the_scope_is_not_empty():
    """Non-vacuity: everything below iterates these two sets."""
    found = _packages_the_dags_import()
    assert found, "no repo package imported by any DAG — this guard is blind"
    assert {"src", "tools"} <= found, (
        f"the two packages this brick is about are no longer in scope: {sorted(found)}")
    assert _mounts(TEMPLATE), "no mount parsed from the template — the format moved"


def test_the_exclusion_list_stays_small_and_justified():
    """An exclusion list is how a guard quietly stops guarding. One entry, one reason,
    and it must never grow to swallow a package the DAGs really need mounted."""
    assert _RUNTIME_PROVIDED == {"airflow"}, (
        f"something was added to the runtime-provided list: {sorted(_RUNTIME_PROVIDED)}. "
        "Each entry silences this guard for one package — justify it here or drop it.")


@pytest.mark.parametrize("pkg", sorted(_packages_the_dags_import()))
def test_the_template_mounts_every_package_a_dag_imports(pkg):
    mounted = [t for _, t in _mounts(TEMPLATE)]
    assert mounted.count(pkg) == len(_DAG_SERVICES), (
        f"`{pkg}` is imported by a DAG and mounted into {mounted.count(pkg)} of "
        f"{len(_DAG_SERVICES)} Airflow services in docker-compose.example.yml. The "
        "checks that use it will answer 'could not run', and that reaches the alert "
        "subject line as a red preflight.")


def test_tools_is_mounted_read_only_in_the_template():
    """Operator scripts are read by the container, never written by it — and this is
    how production mounts them."""
    assert TEMPLATE.read_text(encoding="utf-8").count(
        "./tools:/opt/airflow/tools:ro") == len(_DAG_SERVICES)


@pytest.mark.skipif(not LOCAL.exists(),
                    reason="docker-compose.yml is gitignored and absent here (CI)")
@pytest.mark.parametrize("pkg", sorted(_packages_the_dags_import()))
def test_the_local_copy_has_not_drifted_from_the_template(pkg):
    """The file that actually ran, and the only one that was wrong.

    Skipped in CI by construction, which is the honest thing: CI has no such file.
    On a developer's machine it is the only guard that can see this drift at all.
    """
    mounted = [t for _, t in _mounts(LOCAL)]
    assert mounted.count(pkg) == len(_DAG_SERVICES), (
        f"your local docker-compose.yml mounts `{pkg}` into {mounted.count(pkg)} of "
        f"{len(_DAG_SERVICES)} Airflow services; the template mounts it into all "
        "three. Re-derive it from docker-compose.example.yml.")
