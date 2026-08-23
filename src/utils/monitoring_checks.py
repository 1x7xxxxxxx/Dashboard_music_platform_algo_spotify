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


def tenant_freshness_gaps(per_tenant, declared_by_artist=None) -> list:
    """Per-tenant stale PLATFORMS — `check_data_freshness` ran GLOBALLY, so a tenant with
    no data on platform Y was masked whenever another tenant had recent data.

    `per_tenant`: iterable of `(artist_id, artist_name, results)` where results is the
    list of freshness dicts returned by `check_freshness(db, artist_id)`.
    `declared_by_artist`: optional `{artist_id: {logical platform, …}}`. When given, a
    platform the tenant never declared is not reported — see below.

    Three measured suppressions, no exclusion list anywhere. Each answers a question
    about THIS tenant, so a doubt keeps the alert.

    1. **Best-of-sources, per platform.** A platform can be proven by more than one
       source (Spotify: the API table *or* the S4A CSV). `artist_readiness` has always
       kept the BEST of them (`_RANK`); this function reported EACH of them. So an
       artist who uses the API and never uploads a CSV was reported stale on
       "Spotify S4A" every single night while their Spotify was perfectly fresh. That
       one line is most of the permanent noise: it fires for every API-only tenant.
    2. **A platform the tenant never declared is not a gap.** It is a platform they do
       not use. The input is `declared_identities()` — a fact read from the credentials
       store, not a name someone typed. Absent the map, nothing is suppressed.
    3. **A source no platform claims is not attributable to a tenant.** "Apple Music"
       is in `MONITOR_TARGETS` but in no `SOURCES_FOR_PLATFORM` entry, so
       `artist_readiness` never scores it — while this function reported it stale for
       every tenant who has never uploaded an Apple CSV. It stays monitored globally,
       where it belongs.

    `expected_silence` is honoured for free: `check_freshness` already sets
    `stale=False` when it has MEASURED a reason for the silence.
    """
    from src.utils.freshness_monitor import SOURCES_FOR_PLATFORM

    # Derived from the registry, never restated: {source label -> logical platform}
    platform_of_source = {src: platform
                          for platform, sources in SOURCES_FOR_PLATFORM.items()
                          for src in sources}

    gaps = []
    for artist_id, artist_name, results in per_tenant:
        declared = (declared_by_artist or {}).get(artist_id)

        by_platform: dict[str, list[dict]] = {}
        for r in (results or []):
            platform = platform_of_source.get(r.get('source'))
            if platform is None:
                continue                      # (3) claimed by no platform
            if declared is not None and platform not in declared:
                continue                      # (2) not declared by this tenant
            by_platform.setdefault(platform, []).append(r)

        stale = sorted(
            r['source']
            for platform, rows in by_platform.items()
            # (1) a platform is a gap only when EVERY source that could prove it is stale
            if all(x.get('stale') for x in rows)
            for r in rows
        )
        if stale:
            gaps.append({
                'artist_id': artist_id, 'artist_name': artist_name, 'stale_sources': stale,
            })
    return gaps
