"""
Guard — a check that exists is wired, runs, and reaches the send decision.

Type: Sub
Uses: ast, pathlib
Triggers: pytest
Depends on: airflow/dags/alert_monitor.py
Persists in: nothing (read-only assertions)

Error classes: finding-rendered-but-not-alerted, detector-written-and-never-called.

Two failures this repository has already paid for, one after the other:

  * 2026-08-21 — `central_apps_broken` was rendered in the email BODY and first in the
    SUBJECT, but was absent from `has_issues`, the expression that decides whether any
    email is sent at all. A broken shared app, alone, produced NOTHING. It was masked
    only because Meta happened to be stale at the same time.
  * 2026-08-23 — `tools/tenant_contamination_check.py::scan()` was reachable only from
    `make tenant-check` and from step 5 of `artist_preflight`, and
    `check_canary_preflight` runs steps 2-4. So the ONE class this repo has actually
    been bitten by — a tenant's rows filed under another tenant for months — was the
    one class with no watchdog.

`test_alert_monitor_sends_what_it_finds.py` already pins the second half (every pulled
xcom takes part in `has_issues`). This file pins the FIRST half, which nothing covered:
a `check_*` function that exists must have an operator and be upstream of the sender.
Both are read off the AST — a check named only in a comment does not run.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ALERT_MONITOR = ROOT / "airflow" / "dags" / "alert_monitor.py"

_TREE = ast.parse(ALERT_MONITOR.read_text(encoding="utf-8"))


def _check_functions(tree: ast.Module | None = None) -> list[str]:
    """Every module-level `def check_*` — derived, never hand-listed."""
    tree = _TREE if tree is None else tree
    return sorted(n.name for n in tree.body
                  if isinstance(n, ast.FunctionDef) and n.name.startswith("check_"))


def _callables_given_to_operators(tree: ast.Module | None = None) -> set[str]:
    """`python_callable=X` on any PythonOperator, read off the AST."""
    out = set()
    for node in ast.walk(_TREE if tree is None else tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg == "python_callable" and isinstance(kw.value, ast.Name):
                out.add(kw.value.id)
    return out


def _task_vars_upstream_of_the_sender(tree: ast.Module | None = None) -> set[str]:
    """Names inside the list that is `>>`-ed into the alert task."""
    out = set()
    for node in ast.walk(_TREE if tree is None else tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.RShift):
            if isinstance(node.left, ast.List):
                out.update(e.id for e in node.left.elts if isinstance(e, ast.Name))
    return out


def test_the_scope_is_not_empty() -> None:
    checks = _check_functions()
    assert len(checks) >= 10, f"derived only {checks} — the AST walk is wrong"


@pytest.mark.parametrize("check", _check_functions())
def test_a_check_that_exists_has_an_operator(check: str) -> None:
    assert check in _callables_given_to_operators(), (
        f"{check}() is defined in alert_monitor.py but no PythonOperator calls it. "
        "A detector nobody schedules is decoration — it is the shape that left the "
        "contamination scan without a watchdog for months."
    )


def test_every_operator_is_upstream_of_the_sender() -> None:
    """An operator that exists but is not wired never runs, and says nothing."""
    upstream = _task_vars_upstream_of_the_sender()
    assert len(upstream) >= 12, (
        f"only {len(upstream)} task(s) feed the alert task: {sorted(upstream)}. "
        "A task defined and left out of the dependency list is scheduled by nobody."
    )

    # Every t_* operator assigned at module level must be in that list (or BE the sender).
    assigned = set()
    for node in ast.walk(_TREE):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id.startswith("t_"):
                    assigned.add(tgt.id)
    orphans = sorted(assigned - upstream - {"t_alert"})
    assert not orphans, (
        f"these operators are defined but never wired into the DAG: {orphans}"
    )


def unheard(tree: ast.Module) -> list[str]:
    """Checks with no operator, and operators nobody wires to the sender. Pure."""
    scheduled = _callables_given_to_operators(tree)
    out = [f"{c}: no operator" for c in _check_functions(tree) if c not in scheduled]
    upstream = _task_vars_upstream_of_the_sender(tree)
    assigned = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign)
                for t in n.targets if isinstance(t, ast.Name) and t.id.startswith("t_")}
    out += [f"{t}: not wired" for t in sorted(assigned - upstream - {"t_alert"})]
    return out


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: the contamination scan of 2026-08 — a `check_*` defined with no
    operator — and an operator left out of the dependency list are both named; a
    check scheduled and wired upstream of the sender is not."""
    dag = ("def check_freshness(): pass\n"
           "def check_contamination(): pass\n"
           "t_fresh = PythonOperator(task_id='f', python_callable=check_freshness)\n"
           "t_orphan = PythonOperator(task_id='o', python_callable=check_freshness)\n"
           "t_alert = PythonOperator(task_id='a', python_callable=send)\n"
           "[t_fresh] >> t_alert\n")
    assert unheard(ast.parse(dag)) == ["check_contamination: no operator",
                                       "t_orphan: not wired"]
    fixed = dag.replace("t_orphan = PythonOperator(task_id='o', python_callable=check_freshness)",
                        "t_scan = PythonOperator(task_id='s', python_callable=check_contamination)"
                        ).replace("[t_fresh] >> t_alert", "[t_fresh, t_scan] >> t_alert")
    assert unheard(ast.parse(fixed)) == []


def test_every_check_is_scheduled_and_wired() -> None:
    assert unheard(_TREE) == []
