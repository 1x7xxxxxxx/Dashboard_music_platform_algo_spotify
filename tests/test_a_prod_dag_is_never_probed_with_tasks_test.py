"""An `airflow tasks test` run against PRODUCTION over ssh is refused by the Bash hook.

Type: Sub
Uses: .claude/hooks/guard_destructive.py (_tasks_test_on_prod, check_command)
Depends on: nothing
Persists in: nothing

R191 (2026-09-26). Twice that day `airflow tasks test alert_monitor send_consolidated_alert`
ran on the production box: Airflow 2.11 leaves a temporary DagRun that the scheduler then
executes in full — every task, every mail. The second time three tasks deadlocked on
Airflow's metadata DB and a false « FAILED » reached the owner's inbox. The hook reads the
command's STRUCTURE: prose that merely mentions the gesture must stay allowed.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "guard_destructive.py"
_spec = importlib.util.spec_from_file_location("guard_destructive_r191", _HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """The measured gesture is blocked; the safe forms and the prose about it are not."""
    measured = ("ssh root@167.233.92.1 'cd /opt/streamlytics; docker compose exec -T "
                "airflow-scheduler airflow tasks test alert_monitor send_consolidated_alert'")
    assert hook._tasks_test_on_prod(measured) == "root@167.233.92.1"
    assert hook.check_command(measured)[0] == "block"
    with_opts = "ssh -o ConnectTimeout=15 root@167.233.92.1 'airflow tasks test d t'"
    assert hook._tasks_test_on_prod(with_opts)
    for allowed in (
        "ssh root@167.233.92.1 'docker compose exec -T airflow-scheduler airflow dags list-import-errors'",
        "ssh root@167.233.92.1 'airflow dags trigger alert_monitor'",
        "docker compose exec airflow-scheduler airflow tasks test d t",
        "echo \"never ssh root@167.233.92.1 'airflow tasks test d t'\"",
        "ssh other@10.0.0.1 'airflow tasks test d t'",
    ):
        assert hook._tasks_test_on_prod(allowed) is None, allowed
