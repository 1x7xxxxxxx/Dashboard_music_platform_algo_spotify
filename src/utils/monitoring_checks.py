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


def silent_zero_findings(rows) -> list:
    """Configured tenant×platform with ZERO recent rows — the silent-success class.

    `rows`: iterable of (artist_id, artist_name, platform, configured: bool, rows_recent: int).
    A collector that catches an error and writes nothing exits the DAG SUCCESS; the row-spike
    check never fires on zero. Flag any platform the artist IS configured for that produced no
    data in the lookback window.
    """
    findings = []
    for artist_id, artist_name, platform, configured, rows_recent in rows:
        if configured and (rows_recent or 0) == 0:
            findings.append({
                'artist_id': artist_id, 'artist_name': artist_name, 'platform': platform,
            })
    return findings


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
