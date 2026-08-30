"""How long a DAG run may last before Airflow must call it dead.

Type: Utility
Uses: datetime.timedelta
Triggers: nothing
Depends on: nothing (importable outside a container — the tests rely on that)
Persists in: nothing

The defect this exists for
--------------------------
On 2026-08-30 not one of the 16 DAGs declared `dagrun_timeout`. Airflow's default
is None: a run that hangs hangs forever, holds its slot, and — this is the part
that bites — can still be recorded **success**. Measured on the whole production
history of `dag_run`:

    dag                       p50      p95        max
    data_quality_check     63654.8  63654.8    63654.8   (17.7 h, one run, "success")
    alert_monitor              3.4      8.1    47287.1   (13.1 h, "success")
    meta_ads_api_daily       119.7   1953.0     3534.6
    imusician_csv_watcher      3.1      4.1      604.5
    distrokid_csv_watcher      3.1      4.1      603.3
    soundcloud_daily           3.0     11.1      352.0
    instagram_daily           18.6     25.3       35.7
    ... every other DAG      < 4.5    < 8.1      < 16

`alert_monitor` is the one that matters: the nightly alert channel, normally 3.4
seconds, once ran for thirteen hours and reported success. For those thirteen
hours nothing could have told anyone the alerting was hung — a silent monitor is
indistinguishable from a quiet night, which is the failure mode
`infra_health_cron.sh` was built to catch from the other side.

How these numbers were chosen
-----------------------------
Not from the observed maximum. On the two DAGs that matter, **the maximum IS the
pathology** — calibrating on it would set `alert_monitor` at thirteen hours and
guarantee the guard never fires. The rule is:

    timeout = max(4 x p95, FLOOR)

p95 describes the slow-but-real runs; 4x leaves room for a genuinely bad night
(an API retrying, a CSV backlog); the floor keeps every short DAG from being
killed by a one-off blip on a busy host. Only `meta_ads_api_daily` earns more
than the floor, and it earns it honestly: its p95 really is 33 minutes of Meta
pagination.

A timeout is a statement about the SHAPE of a run, not a performance target. It
must never fire on a healthy run — if one does, raise it and write down why,
rather than deleting it.
"""
from __future__ import annotations

from datetime import timedelta

# The floor. Two orders of magnitude above the p95 of every DAG except one, so a
# healthy run cannot reach it; three orders of magnitude below the hangs above, so
# a hang cannot hide behind it.
FLOOR = timedelta(minutes=30)

# Per-DAG overrides, keyed on dag_id. Seconds, from `4 x p95` on the production
# history read on 2026-08-30. Anything not listed gets FLOOR.
OVERRIDES: dict[str, timedelta] = {
    # p95 = 1953 s (32.5 min) of Meta Ads pagination — the only DAG whose normal
    # slow path exceeds the floor. 4 x p95 is 2 h 10, so 2 h was too tight; the
    # test caught that before this shipped, which is the point of deriving the
    # bound from the measurement instead of restating the constant.
    "meta_ads_api_daily": timedelta(hours=3),
    # Paused since 2026-08-23 (R46) and its single recorded run took 17.7 h. If it
    # is ever resumed it must not be able to do that again.
    "data_quality_check": timedelta(hours=1),
}


def dagrun_timeout_for(dag_id: str) -> timedelta:
    """The `dagrun_timeout` a DAG must declare. Never None."""
    return OVERRIDES.get(dag_id, FLOOR)
