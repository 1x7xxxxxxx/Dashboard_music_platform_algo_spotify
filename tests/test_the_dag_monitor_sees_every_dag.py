"""A DAG monitor that shows 4 of 16 DAGs is not slow — it is wrong.

Type: Test
Uses: ast, requests (skipped when Airflow is unreachable)
Depends on: src/dashboard/utils/airflow_monitor.py
Persists in: nothing

The defect
----------
`get_all_dags_last_state()` POSTed once to `/dags/~/dagRuns/list` with a
`page_limit` window and took whatever came back. Its own docstring stated the
assumption:

    "with daily schedules each DAG's latest run sits well within 200"

Production broke it. Measured 2026-08-30: **392 dag runs in 24 h, 384 of them from
the four CSV watchers** (96 each, every 15 minutes). The 200-run window therefore
spanned ~12 hours and was 98 % four DAGs.

    batch, page_limit=200    254 ms   1 call    4 of 16 DAGs
    batch + dag_ids filter   194 ms   1 call    4 of 16 DAGs  (API caps page_limit
                                                               at 100 — filtering
                                                               does not help)
    per-DAG, sequential     1315 ms  16 calls  16 of 16
    per-DAG, 8 threads       440 ms  16 calls  16 of 16

`views/home.py` renders DAG health from this call. **Twelve of sixteen DAGs showed
as "no run"** on the landing page — on screen, indistinguishable from a DAG that
genuinely had not run. Nothing could report it: every request returned 200.

Why this guard asks about COMPLETENESS
--------------------------------------
The obvious test after an N+1 fix counts HTTP calls, and it would have passed on the
broken version with flying colours — one call instead of sixteen. It measures the
thing that was optimised rather than the thing that was promised. The question that
catches this defect is *did it come back with every DAG?*, so that is the assertion.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_MONITOR = _ROOT / "src" / "dashboard" / "utils" / "airflow_monitor.py"


def _monitor_or_skip():
    """A live AirflowMonitor, or a loud skip. Never a silent pass."""
    try:
        from src.dashboard.utils.airflow_monitor import AirflowMonitor
    except Exception as e:                       # noqa: BLE001
        pytest.skip(f"airflow_monitor not importable here: {type(e).__name__}: {e}")
    monitor = AirflowMonitor()
    try:
        resp = monitor.session.get(f"{monitor.base_url}/dags",
                                   params={'limit': 1}, timeout=5)
        if resp.status_code != 200:
            pytest.skip(f"Airflow API answered {resp.status_code} — nothing to assert")
    except Exception as e:                       # noqa: BLE001
        pytest.skip(f"Airflow API unreachable ({type(e).__name__}) — "
                    "this guard needs a live scheduler to mean anything")
    return monitor


def test_the_latest_state_call_returns_every_dag():
    """The load-bearing one. Not 'how many calls' — 'how many DAGs came back'."""
    monitor = _monitor_or_skip()
    expected = set(monitor.get_dag_list())
    if not expected:
        pytest.skip("Airflow reports no DAGs at all")

    got = set(monitor.get_all_dags_last_state())
    missing = expected - got

    # A DAG that has genuinely never run is legitimately absent, so only fail when a
    # missing DAG DOES have a run — that is the window truncating, not an idle DAG.
    truly_missing = [d for d in sorted(missing) if monitor.get_runs_for_dag(d, limit=1)]
    assert not truly_missing, (
        f"get_all_dags_last_state() returned {len(got)} of {len(expected)} DAGs. "
        f"These have runs in Airflow but came back empty: {truly_missing}.\n"
        "On `home` they render as 'no run' — indistinguishable from a DAG that never "
        "ran. This is the page-window defect of 2026-08-30; do not reintroduce a "
        "global `page_limit` over a fleet whose run counts differ by 100x."
    )


def test_the_run_table_covers_every_unpaused_dag():
    """Same question for `get_dag_runs`, which feeds the airflow_kpi view."""
    monitor = _monitor_or_skip()
    df = monitor.get_dag_runs()
    if df.empty:
        pytest.skip("no runs recorded in this Airflow")

    resp = monitor.session.get(f"{monitor.base_url}/dags", params={'limit': 100})
    unpaused = {d['dag_id'] for d in resp.json().get('dags', [])
                if not d.get('is_paused')}
    got = set(df['dag_id'].unique())
    missing = [d for d in sorted(unpaused - got)
               if monitor.get_runs_for_dag(d, limit=1)]
    assert not missing, (
        f"get_dag_runs() covers {len(got)} of {len(unpaused)} unpaused DAGs; "
        f"{missing} have runs but are absent from the table."
    )


def test_the_fetch_is_concurrent_and_bounded():
    """Structure, read from the tree — the 3x speed-up must not silently regress.

    Asserted on the AST rather than by timing: a wall-clock assertion in CI would be
    flaky on a loaded runner, and would fail for reasons that have nothing to do with
    the code.
    """
    tree = ast.parse(_MONITOR.read_text(encoding="utf-8"))
    fn = next((f for f in ast.walk(tree)
               if isinstance(f, ast.FunctionDef) and f.name == "_runs_per_dag"), None)
    assert fn is not None, (
        "_runs_per_dag is gone — the per-DAG fetch is no longer factored in one place, "
        "and the next caller will re-derive the sequential version."
    )
    pool = next((n for n in ast.walk(fn)
                 if isinstance(n, ast.Call)
                 and getattr(n.func, "id", "") == "ThreadPoolExecutor"), None)
    assert pool is not None, "_runs_per_dag no longer fetches concurrently"

    workers = next((kw.value for kw in pool.keywords if kw.arg == "max_workers"), None)
    assert isinstance(workers, ast.Constant) and 2 <= workers.value <= 8, (
        "max_workers must stay within 2..8. Measured 2026-08-30 against production: "
        "8 workers 440 ms, 16 workers 475 ms — past 8 it gets SLOWER, because the "
        "Airflow webserver runs 4 gunicorn processes and extra threads only queue."
    )


def test_no_global_page_window_is_used_to_answer_a_per_dag_question():
    """The specific shape that produced the defect must not come back.

    `page_limit` over `/dags/~/dagRuns/list` is a fleet-wide window; using it to
    answer "latest run of each DAG" is only correct when every DAG runs at the same
    rate. Here they differ by 100x (96/day against 1/week).
    """
    body = _MONITOR.read_text(encoding="utf-8")
    tree = ast.parse(body)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "post":
            continue
        payload = next((kw.value for kw in node.keywords if kw.arg == "json"), None)
        if payload is None or not isinstance(payload, ast.Dict):
            continue
        keys = {k.value for k in payload.keys if isinstance(k, ast.Constant)}
        assert "page_limit" not in keys, (
            f"{_MONITOR.name}:{node.lineno} POSTs a fleet-wide `page_limit` window "
            "again. That is the 2026-08-30 defect: 4 of 16 DAGs returned, and `home` "
            "showed the other 12 as 'no run'."
        )
