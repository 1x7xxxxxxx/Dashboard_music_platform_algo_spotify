"""
Guard — every collection DAG records a per-tenant outcome in etl_run_log.

Type: Sub
Uses: ast, pathlib
Triggers: pytest
Depends on: airflow/dags/*.py, src/utils/dag_run_logger.py
Persists in: nothing (read-only assertions)

Error class: per-tenant-outcome-not-recorded.

Measured in production 2026-08-23: `etl_run_log` had, over its ENTIRE history, rows
for exactly two dag_ids — `meta_ads_api_daily` (195) and `meta_insights_watcher` (13,
stopped in May). Spotify, YouTube, SoundCloud and Instagram had never written a single
row. So the one table that can answer "did collection run for THIS tenant?" was blind
on four platforms out of five, and three dashboard surfaces that read it
(`views/etl_logs.py`, `views/alerts.py`, the `has_runs` KPI in `views/home.py`) were
blind with it.

What that cost, concretely: `youtube_daily` reported SUCCESS every night while Benken
(tenant 12) failed inside its per-tenant `try`. The only trace was a WARNING line, and
the task's return value did not even mention the tenant. Freshness eventually turned
the tenant `stale`, and `readiness_red_flags` excludes `stale` — so nobody was told.

The scope is DERIVED from the tree: any DAG whose module loads per-tenant credentials
is a collection DAG. A hand-written list would protect exactly the DAGs someone
remembered — which is how this gap survived from the beginning.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DAGS = ROOT / "airflow" / "dags"

# The three outcomes a tenant-scoped run can have. `skipped` is not optional: a tenant
# who declared no identity is CORRECT, but must still leave a row — absence of a row is
# indistinguishable from "the DAG never looked at this tenant".
_RECORDERS = {"record_tenant_success", "record_tenant_failure", "record_tenant_skip"}


def _collection_dags() -> list[str]:
    """DAGs that COLLECT — derived from the tree, never hand-listed.

    The predicate is "imports something from `src.collectors`", read off the AST. The
    first version asked "touches per-tenant credentials", which also caught
    `alert_monitor`, `data_quality_check`, `onboarding_report` and `meta_token_refresh`
    — they read credentials to WATCH or to REFRESH, and have no tenant collection
    outcome to record. A guard that fires on those teaches people to ignore it.
    """
    out = []
    for path in sorted(DAGS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                    "src.collectors"):
                out.append(path.name)
                break
    return out


def _called_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def test_the_scope_is_not_empty() -> None:
    """A derived scope that silently matches nothing is a guard that does not run."""
    dags = _collection_dags()
    assert len(dags) >= 5, f"expected the collection DAGs, derived only {dags}"


@pytest.mark.parametrize("dag_file", _collection_dags())
def test_a_collection_dag_records_each_tenant_outcome(dag_file: str) -> None:
    called = _called_names(DAGS / dag_file)
    used = called & (_RECORDERS | {"DagRunLogger"})
    assert used, (
        f"{dag_file} resolves per-tenant credentials but writes nothing to etl_run_log. "
        f"A tenant that stops collecting inside the per-tenant try/except leaves no "
        f"trace anywhere: the task stays SUCCESS and its return value omits the tenant. "
        f"Call one of {sorted(_RECORDERS)} at each exit of the per-tenant loop."
    )


@pytest.mark.parametrize("dag_file", _collection_dags())
def test_a_recording_dag_covers_failure_and_skip_too(dag_file: str) -> None:
    """Recording only the happy path is the defect wearing a ledger."""
    called = _called_names(DAGS / dag_file)
    if not (called & _RECORDERS):
        pytest.skip(f"{dag_file} uses the DagRunLogger context manager instead")
    missing = sorted(_RECORDERS - called)
    assert not missing, (
        f"{dag_file} records some tenant outcomes but not {missing}. A ledger that "
        f"only holds successes answers 'who succeeded', never 'who stopped'."
    )


def _recorder_in(stmts) -> bool:
    for st in stmts:
        for node in ast.walk(st):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
                if name in _RECORDERS:
                    return True
    return False


def _uncovered_continues(path: Path) -> list[int]:
    """Every `continue` in a per-tenant loop that leaves no ledger row behind.

    Checking only "is a recorder called somewhere in this file" is not enough, and the
    mutation proved it: `instagram_daily` has two `record_tenant_skip` calls, so
    deleting one left the guard green while a whole exit branch went silent again.
    A ledger with a hole in it reads exactly like a complete one.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad: list[int] = []

    def walk_block(stmts, in_tenant_loop: bool) -> None:
        for i, st in enumerate(stmts):
            if isinstance(st, ast.Continue) and in_tenant_loop:
                if not _recorder_in(stmts[:i]):
                    bad.append(st.lineno)
            for field, value in ast.iter_fields(st):
                if isinstance(value, list) and value and isinstance(value[0], ast.stmt):
                    walk_block(value, in_tenant_loop or _is_tenant_loop(st))

    def _is_tenant_loop(node) -> bool:
        if not isinstance(node, ast.For):
            return False
        return _recorder_in(node.body)

    walk_block(tree.body, False)
    return sorted(set(bad))


@pytest.mark.parametrize("dag_file", _collection_dags())
def test_no_tenant_loop_exit_leaves_the_ledger_silent(dag_file: str) -> None:
    path = DAGS / dag_file
    if not (_called_names(path) & _RECORDERS):
        pytest.skip(f"{dag_file} uses the DagRunLogger context manager instead")
    bad = _uncovered_continues(path)
    assert not bad, (
        f"{dag_file}: the per-tenant loop skips a tenant at line(s) {bad} without "
        f"recording anything. That tenant is then indistinguishable from one the DAG "
        f"never looked at — which is the whole defect this ledger exists to remove."
    )
