"""A datetime compared to an Airflow `UtcDateTime` column carries a time zone.

Type: Sub
Uses: airflow/dags/*.py (read as AST)
Depends on: nothing
Persists in: nothing

R179. `alert_monitor.check_dag_failures` built `cutoff = datetime.now() - timedelta(days=7)`
and compared it to `DagRun.execution_date`. That column is an Airflow `UtcDateTime`, whose
`process_bind_param` raises `ValueError("naive datetime is disallowed")` (Airflow 2.11.0,
`airflow/utils/sqlalchemy.py`). The `except` around the query logged it and returned `{}`:
the nightly mail's "failed DAGs" section was empty from 2026-03-25 on.
"""
from __future__ import annotations

import ast
from pathlib import Path

_DAGS = Path(__file__).resolve().parents[1] / "airflow" / "dags"
_AIRFLOW_MODELS = {"DagRun", "TaskInstance", "DagModel", "Log", "XCom", "SlaMiss"}


def _naive_now(node: ast.AST) -> bool:
    """`datetime.now()` / `datetime.utcnow()` with no tz argument, anywhere in `node`."""
    return any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
               and c.func.attr in ("now", "utcnow") and not c.args and not c.keywords
               and getattr(c.func.value, "id", "") == "datetime"
               for c in ast.walk(node))


def naive_cutoffs_bound_to_airflow(source: str) -> list[int]:
    """Lines where a name assigned from a naive `datetime.now()` is compared to a column
    of an Airflow ORM model. Pure."""
    tree = ast.parse(source)
    naive = {t.id: n.lineno for n in ast.walk(tree) if isinstance(n, ast.Assign)
             and _naive_now(n.value) for t in n.targets if isinstance(t, ast.Name)}
    out = []
    for c in ast.walk(tree):
        if not isinstance(c, ast.Compare):
            continue
        left = c.left
        if not (isinstance(left, ast.Attribute)
                and getattr(left.value, "id", "") in _AIRFLOW_MODELS):
            continue
        for right in c.comparators:
            if (isinstance(right, ast.Name) and right.id in naive) or _naive_now(right):
                out.append(c.lineno)
    return sorted(out)


def test_no_dag_binds_a_naive_datetime_to_an_airflow_column() -> None:
    offenders = [f"{p.name}:{line}" for p in sorted(_DAGS.glob("*.py"))
                 for line in naive_cutoffs_bound_to_airflow(p.read_text(encoding="utf-8"))]
    assert not offenders, (
        f"{offenders} : une date NAÏVE comparée à une colonne `UtcDateTime` d'Airflow. "
        "Airflow la refuse (`naive datetime is disallowed`) ; si un `except` l'entoure, la "
        "requête rend « rien » en silence. `datetime.now(timezone.utc)`.")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: the R179 shape — a naive cutoff compared to `DagRun.execution_date` —
    is named, inline or through a name; the tz-aware cutoff, and a naive date compared
    to something that is not an Airflow column, are not."""
    bad = ("cutoff = datetime.now() - timedelta(days=7)\n"
           "q = session.query(DagRun).filter(DagRun.execution_date >= cutoff)\n")
    inline = "q = session.query(DagRun).filter(DagRun.start_date < datetime.utcnow())\n"
    assert naive_cutoffs_bound_to_airflow(bad) == [2]
    assert naive_cutoffs_bound_to_airflow(inline) == [1]
    good = bad.replace("datetime.now()", "datetime.now(timezone.utc)")
    local = "cutoff = datetime.now()\nif row.created_at >= cutoff:\n    pass\n"
    assert naive_cutoffs_bound_to_airflow(good) == []
    assert naive_cutoffs_bound_to_airflow(local) == []
