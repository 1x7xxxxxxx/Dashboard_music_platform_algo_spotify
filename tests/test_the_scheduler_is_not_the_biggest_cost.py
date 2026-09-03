"""Guard: Airflow's cost stays proportionate to what it orchestrates.

Type: Utility
Uses: ast, pathlib, re
Triggers: pytest
Persists in: nothing

Error class `orchestrator-costs-more-than-what-it-orchestrates`.

Measured 2026-09-04, starting from the observation that Airflow held 1,6 GB of RAM
against a 43 MB application database.

The premise needed correcting first, and that matters: **878 MB scheduler + 903 MB
webserver is the Python processes themselves**, not run history — cutting executions
does not hand that memory back. What it hands back is CPU, disk, and scheduler churn.
And the CPU was real: **scheduler at 28,9 %, webserver at 0,33 %**.

## What was actually costing

| Measure | Before |
|---|---|
| Airflow metadata database | **246 MB** — six times the 43 MB it orchestrates |
| History retained | 83 days, since 2026-06-13, **`airflow db clean` never run** |
| The four `*_csv_watcher` share | **97,2 % of dag_run**, **98,4 % of task_instance** |
| Their executions | 1 536/day, every one `skipped` |
| The directories they poll | **empty** — `find` returned no file at all |

## What changed, in order of measured effect

1. `min_file_process_interval` 30 s → 300 s. The 16 DAG files were re-parsed every
   30 seconds. **CPU 28,9 % → 2,45 %, scheduler RAM 878 → 622 MB.**
2. The watchers went from `*/15` to hourly: 1 536 → 384 runs/day.
3. `tools/airflow_db_clean.sh`, weekly, retention 30 days. **246 MB → 91 MB** after
   the first pass plus a `VACUUM FULL` (the DELETE alone returns nothing to the OS).

Deliberately NOT done: merging the four watchers into one. At hourly cadence that
saves 72 runs/day for a refactor touching 4 DAGs, 4 debug scripts and their parsers.
The lever was the cadence, not the DAG count — and ADR-007's discipline says spending
risk against a benefit measured near zero is the defect, not the fix.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


REPO = _repo_root()
DAGS = REPO / "airflow" / "dags"
COMPOSE = REPO / "docker-compose.example.yml"


def test_no_watcher_polls_more_than_hourly():
    """A quarter-hourly poll on a directory nobody writes to is 98 % of the metadata."""
    offenders = []
    for dag in sorted(DAGS.glob("*_csv_watcher.py")):
        # AST, not a regex: a DAG file is Python, and its `schedule=` may appear in a
        # comment, a docstring, or a second DAG object. `test_a_guard_reads_structure_
        # not_text` flagged the first version of this file for exactly that — the
        # ratchet doing its job on the guard that had just been written.
        tree = ast.parse(dag.read_text(encoding="utf-8"))
        schedules = [kw.value.value for node in ast.walk(tree)
                     if isinstance(node, ast.Call)
                     for kw in node.keywords
                     if kw.arg == "schedule" and isinstance(kw.value, ast.Constant)
                     and isinstance(kw.value.value, str)]
        assert schedules, f"{dag.name} declares no schedule"
        assert len(schedules) == 1, (
            f"{dag.name} declares {len(schedules)} schedules; this guard reads one"
        )
        minute_field = schedules[0].split()[0]
        # `*/N` with N < 60, or a bare `*`, means more than once an hour.
        if minute_field == "*" or (minute_field.startswith("*/")
                                   and int(minute_field[2:]) < 60):
            offenders.append(f"{dag.name}: {schedules[0]}")
    assert not offenders, (
        f"{offenders} poll more than hourly. These four DAGs produced 97,2 % of all "
        "dag_run rows and 98,4 % of all task_instance rows on 2026-09-04, every one "
        "of them `skipped`, against directories that have never held a file."
    )


def test_the_dag_parsing_interval_is_not_the_default():
    """The single biggest lever, and the one nobody sets."""
    body = COMPOSE.read_text(encoding="utf-8")
    m = re.search(r"AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL:\s*['\"]?(\d+)", body)
    assert m, (
        "MIN_FILE_PROCESS_INTERVAL is gone from the compose file. At Airflow's default "
        "of 30 s the 16 DAG files are re-parsed twice a minute: measured 28,9 % "
        "scheduler CPU, against 2,45 % at 300 s."
    )
    assert int(m.group(1)) >= 120, (
        f"the parsing interval is back down to {m.group(1)} s. Below ~2 minutes the "
        "scheduler spends its time re-reading files that change a few times a month."
    )


def test_the_metadata_purge_exists_and_is_non_interactive():
    """`airflow db clean` prompts by default; under cron a prompt hangs forever."""
    script = REPO / "tools" / "airflow_db_clean.sh"
    assert script.is_file(), "tools/airflow_db_clean.sh is gone"
    body = script.read_text(encoding="utf-8")
    assert "airflow db clean" in body
    assert "--yes" in body, (
        "the purge would prompt for confirmation. Run from cron it would block "
        "indefinitely with nothing reporting it — the shape of a silent failure."
    )
    assert "RETENTION_DAYS" in body, "the retention window is not configurable"


def test_the_purge_is_reachable_from_the_repo():
    """A script nobody can find is a script nobody runs — this repo's own lesson.

    `db_restore_test.sh` sat unscheduled from June to September for exactly that
    reason. The cron lives on the box (it cannot be asserted from here), so what is
    pinned instead is that the repo NAMES the script somewhere a reader will meet it.
    """
    named_in = [p.name for p in (REPO / "docs" / "adr").glob("*.md")
                if "airflow_db_clean" in p.read_text(encoding="utf-8")]
    devlog = (REPO / "DEVLOG.md").read_text(encoding="utf-8")
    assert named_in or "airflow_db_clean" in devlog, (
        "nothing in docs/adr or DEVLOG mentions tools/airflow_db_clean.sh. An "
        "operational script referenced by no document is one nobody will schedule "
        "again after a rebuild."
    )
