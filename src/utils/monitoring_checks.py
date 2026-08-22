"""Pure detection logic for the alert_monitor DAG (no Airflow / DB imports).

Type: Utility
Uses: nothing (pure functions over plain data)
Depends on: nothing
Persists in: nothing

Extracted so the monitoring RULES are unit-testable without importing Airflow (the
alert_monitor DAG module imports airflow, which isn't installed in the test venv). The DAG
fetches rows from Postgres / the Airflow metadata DB and passes plain tuples here. Each
function targets a silent failure mode the Benken week exposed.
"""
from datetime import date, datetime, timedelta


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def consecutive_failure_days(runs, min_days: int = 3) -> dict:
    """DAGs that failed on >= min_days CONSECUTIVE calendar days ending at their latest run.

    `runs`: iterable of (dag_id, execution_date, state). A 7-day *total count* (the prior
    logic) can't tell "2 isolated failures" from "failing every single day" — this does,
    so a DAG broken for days (youtube/soundcloud/instagram in the Benken week) escalates.
    Returns {dag_id: streak_len} for streaks >= min_days.
    """
    by_dag: dict = {}
    for dag_id, exec_date, state in runs:
        d = _as_date(exec_date)
        if d is None:
            continue
        # Latest state for a given calendar date wins.
        by_dag.setdefault(dag_id, {})[d] = state

    out = {}
    for dag_id, day_state in by_dag.items():
        if not day_state:
            continue
        cur = max(day_state)
        streak = 0
        while day_state.get(cur) == 'failed':
            streak += 1
            cur = cur - timedelta(days=1)
        if streak >= min_days:
            out[dag_id] = streak
    return out


# `silent_zero_findings` lived here from its introduction until 2026-08-22 and was
# never called by anything but its own unit test. It computed "configured tenant ×
# platform with zero recent rows" — which is precisely the predicate
# `artist_readiness.platform_status` already computes as NO_DATA, and
# `readiness_red_flags` already feeds to the nightly alert.
#
# So it was not a missing guard, it was a SECOND one for a fact that already had a
# reader. Waking it would have produced two voices for one finding, which this repo
# names `watchdog-becomes-the-noise`; leaving it made the catalogue look like the
# class was covered twice. Deleted, and the class it was written for is guarded by
# `tests/test_no_detector_is_written_and_never_called.py`.


def tenant_freshness_gaps(per_tenant) -> list:
    """Per-tenant stale sources — `check_data_freshness` ran GLOBALLY, so a tenant with no
    data on platform Y was masked whenever another tenant had recent data.

    `per_tenant`: iterable of (artist_id, artist_name, results) where results is the list of
    freshness dicts (each with 'source' and 'stale') returned by check_freshness(db, artist_id).
    Returns one entry per tenant that has >=1 stale source.
    """
    gaps = []
    for artist_id, artist_name, results in per_tenant:
        stale = [r['source'] for r in (results or []) if r.get('stale')]
        if stale:
            gaps.append({
                'artist_id': artist_id, 'artist_name': artist_name, 'stale_sources': stale,
            })
    return gaps
