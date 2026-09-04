"""No DAG may run forever, and none may be recorded successful after doing so.

Type: Test
Uses: ast
Depends on: airflow/dags/*.py, src/utils/dag_timeouts.py
Persists in: nothing

The defect
----------
On 2026-08-30, none of the 16 DAGs declared `dagrun_timeout`. Airflow's default is
None — a hung run holds its slot indefinitely, and can still finish **success**.
Two had already done it, in production:

    alert_monitor        p50 3.4 s      one run of 47 287 s  (13.1 h) — "success"
    data_quality_check   one run        of 63 655 s          (17.7 h) — "success"

`alert_monitor` is the nightly alert channel. For thirteen hours it was hung and
nothing could say so, because a silent monitor and a quiet night look identical
from the outside.

Why the numbers are pinned here and not only in the module
----------------------------------------------------------
A test that asserts `FLOOR == timedelta(minutes=30)` re-states the constant and
proves nothing: edit the constant, the test follows. What must not drift is the
relationship between the timeout and the MEASURED behaviour of the DAG, so this
file pins the production distribution read on 2026-08-30 and derives the check
from it. If a DAG genuinely gets slower, this fixture is what has to be re-measured
first — that is the intended cost.
"""
from __future__ import annotations

import ast
from datetime import timedelta
from pathlib import Path

import pytest

from src.utils.dag_timeouts import FLOOR, OVERRIDES, dagrun_timeout_for

_ROOT = Path(__file__).resolve().parents[1]
_DAGS = _ROOT / "airflow" / "dags"

# Production `dag_run` history, read 2026-08-30 on 167.233.92.1: p95 seconds over
# every successful run ever recorded. This is the REALITY the timeouts answer to.
# The two pathological maxima (alert_monitor 47 287 s, data_quality_check 63 655 s)
# are deliberately NOT here: they are the thing being caught, not a calibration input.
P95_SECONDS = {
    "meta_ads_api_daily": 1953.0,
    "instagram_daily": 25.3,
    "soundcloud_daily": 11.1,
    "alert_monitor": 8.1,
    "youtube_daily": 7.9,
    "imusician_csv_watcher": 4.1,
    "distrokid_csv_watcher": 4.1,
    "apple_music_csv_watcher": 4.1,
    "s4a_csv_watcher": 4.1,
    "spotify_api_daily": 3.4,
    "weekly_digest": 2.9,
    # Ajouté le 2026-09-04, AUCUN historique de production : ce nombre n'est pas
    # une mesure, c'est celui de son jumeau le plus proche — `weekly_digest`, même
    # forme (parcourir les locataires, envoyer un mail). Il hérite donc du plancher.
    # À relire contre `dag_run` après une trentaine d'exécutions réelles.
    "trial_expiry_reminder": 2.9,
    "ml_scoring_daily": 2.6,
    "onboarding_report": 2.3,
    "ml_outcome_labeling": 1.6,
    "meta_token_refresh": 1.4,
}

# Headroom over p95 for a genuinely bad night (an API retrying, a CSV backlog).
HEADROOM = 4


def _dag_files() -> list[Path]:
    return sorted(_DAGS.glob("*.py"))


def _dag_call(tree: ast.Module) -> ast.Call | None:
    return next((n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and getattr(n.func, "id", None) == "DAG"), None)


def _dag_id(call: ast.Call) -> str | None:
    if call.args and isinstance(call.args[0], ast.Constant):
        return call.args[0].value
    return next((kw.value.value for kw in call.keywords
                 if kw.arg == "dag_id" and isinstance(kw.value, ast.Constant)), None)


def dags_without_timeout(paths: list[Path]) -> list[str]:
    """`file` for every DAG whose DAG(...) call declares no dagrun_timeout."""
    bad = []
    for p in paths:
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        call = _dag_call(tree)
        if call is None:
            continue
        if not any(kw.arg == "dagrun_timeout" for kw in call.keywords):
            bad.append(p.name)
    return sorted(bad)


def test_every_dag_declares_a_dagrun_timeout():
    missing = dags_without_timeout(_dag_files())
    assert not missing, (
        "These DAGs can run forever and still report success:\n  "
        + "\n  ".join(missing)
        + "\n\nAdd `dagrun_timeout=dagrun_timeout_for('<dag_id>')` to the DAG(...) call."
    )


def test_the_guard_goes_red_when_a_timeout_is_removed(tmp_path):
    """Mutation: a DAG without the argument must be seen. A red never observed
    does not distinguish 'every DAG is covered' from 'the check reads nothing'."""
    mutant = tmp_path / "mutant_dag.py"
    mutant.write_text(
        "from airflow import DAG\n"
        "with DAG('mutant', schedule='@daily', catchup=False) as dag:\n"
        "    pass\n", encoding="utf-8")
    assert dags_without_timeout([mutant]) == ["mutant_dag.py"]

    ok = tmp_path / "ok_dag.py"
    ok.write_text(
        "from airflow import DAG\n"
        "from src.utils.dag_timeouts import dagrun_timeout_for\n"
        "with DAG('ok', schedule='@daily', catchup=False,\n"
        "         dagrun_timeout=dagrun_timeout_for('ok')) as dag:\n"
        "    pass\n", encoding="utf-8")
    assert dags_without_timeout([ok]) == []


@pytest.mark.parametrize("dag_id,p95", sorted(P95_SECONDS.items()))
def test_the_timeout_clears_the_measured_p95_with_headroom(dag_id, p95):
    """Never fire on a healthy run: the timeout must exceed 4x the measured p95."""
    allowed = dagrun_timeout_for(dag_id)
    assert allowed >= timedelta(seconds=HEADROOM * p95), (
        f"{dag_id}: timeout {allowed} is under {HEADROOM}x its measured p95 "
        f"({p95:.1f}s) — a slow-but-healthy run would be killed."
    )


def test_the_timeout_still_catches_the_two_hangs_that_happened():
    """And the other side: it must be well under the runs it exists to stop."""
    assert dagrun_timeout_for("alert_monitor") < timedelta(seconds=47287), (
        "alert_monitor's timeout no longer catches its own 13.1 h run."
    )
    assert dagrun_timeout_for("data_quality_check") < timedelta(seconds=63654), (
        "data_quality_check's timeout no longer catches its own 17.7 h run."
    )


def test_every_dag_id_on_disk_is_covered_by_the_measured_table():
    """The fixture must describe the DAGs that exist, not a remembered list.

    A DAG added later with no measurement is not an error — but it must inherit the
    floor, and this test is where that gets noticed.
    """
    on_disk = set()
    for p in _dag_files():
        call = _dag_call(ast.parse(p.read_text(encoding="utf-8")))
        if call is not None:
            did = _dag_id(call)
            if did:
                on_disk.add(did)
    unmeasured = on_disk - set(P95_SECONDS) - set(OVERRIDES)
    assert not unmeasured, (
        f"{sorted(unmeasured)} have no measured p95 in this file. Read their real "
        "distribution from production `dag_run` before trusting the floor for them."
    )
    for did in on_disk:
        assert dagrun_timeout_for(did) >= FLOOR or did in OVERRIDES
