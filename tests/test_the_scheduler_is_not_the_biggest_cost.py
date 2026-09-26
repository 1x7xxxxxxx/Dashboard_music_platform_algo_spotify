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
   30 seconds. Sampled over two minutes afterwards, the scheduler **idles at ~2 %**
   with a **~100 % burst per re-parse** — the burst is the same work, it just
   happens ten times less often. Scheduler RAM **878 → 622 MB**.
   (A single `docker stats` sample is not a duty cycle: the first reading after
   the change said 2,45 %, the next said 36,9 %. Both were true instants.)
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

import pytest
from pathlib import Path


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


REPO = _repo_root()
DAGS = REPO / "airflow" / "dags"
COMPOSE = REPO / "docker-compose.example.yml"


def subhourly_schedules(source: str) -> list[str]:
    """`schedule=` literals of a DAG file that fire more than once an hour. Pure."""
    tree = ast.parse(source)
    out = []
    for sched in (kw.value.value for node in ast.walk(tree) if isinstance(node, ast.Call)
                  for kw in node.keywords
                  if kw.arg == "schedule" and isinstance(kw.value, ast.Constant)
                  and isinstance(kw.value.value, str)):
        if not sched or " " not in sched:
            continue  # `@daily` & co : par construction jamais infra-horaires
        minute_field = sched.split()[0]
        # `*/N` with N < 60, or a bare `*`, means more than once an hour.
        if minute_field == "*" or (minute_field.startswith("*/")
                                   and int(minute_field[2:]) < 60):
            out.append(sched)
    return out


def test_the_detector_sees_the_defect_it_is_written_for():
    """Non-vacuity: the quarter-hourly CSV watchers of 2026-09-04 (`*/15`) and a bare
    `*` are named; hourly, daily and a schedule named only in a comment are not."""
    assert subhourly_schedules("DAG('w', schedule='*/15 * * * *')\n") == ["*/15 * * * *"]
    assert subhourly_schedules("DAG('x', schedule='* * * * *')\n") == ["* * * * *"]
    clean = ("# schedule='*/15 * * * *' was the watcher\n"
             "DAG('a', schedule='0 * * * *')\nDAG('b', schedule='@daily')\n")
    assert subhourly_schedules(clean) == []


def test_no_watcher_polls_more_than_hourly():
    """A quarter-hourly poll on a directory nobody writes to is 98 % of the metadata."""
    # TOUS les DAGs, pas seulement les `*_csv_watcher` : ceux-ci ont été supprimés le
    # 2026-09-04, et un garde qui ne cherche que des fichiers absents passe au vert en
    # n'ayant rien vérifié. La règle durable ne porte pas sur ces quatre-là, elle porte
    # sur la cadence — un sondage au quart d'heure sur ce dépôt a produit 98,4 % des
    # lignes de métadonnées Airflow.
    offenders = []
    for dag in sorted(DAGS.glob("*.py")):
        # AST, not a regex: a DAG file is Python, and its `schedule=` may appear in a
        # comment, a docstring, or a second DAG object. `test_a_guard_reads_structure_
        # not_text` flagged the first version of this file for exactly that — the
        # ratchet doing its job on the guard that had just been written.
        offenders += [f"{dag.name}: {sched}"
                      for sched in subhourly_schedules(dag.read_text(encoding="utf-8"))]
    assert not offenders, (
        f"{offenders} run more than once an hour. On 2026-09-04 four such DAGs "
        "produced 97,2 % of all dag_run rows and 98,4 % of all task_instance rows, "
        "every one of them `skipped`. A sub-hourly schedule needs a reason that "
        "survives being asked out loud."
    )
    # Non-vacuité : ce garde doit avoir REGARDÉ quelque chose.
    assert len(list(DAGS.glob("*.py"))) >= 10, (
        "fewer than 10 DAG files found — the glob is pointing at the wrong place and "
        "this test is passing on an empty set."
    )


def test_the_dag_parsing_interval_is_not_the_default():
    """The single biggest lever, and the one nobody sets.

    ⚠️ **Ce test lit le GABARIT, et il a été VERT pendant que le système tournait au
    défaut.** Mesuré le 2026-09-20 (R140 §16.15) :

        $ docker exec airflow_scheduler airflow config get-value \
              scheduler min_file_process_interval
        30

    Le réglage vivait dans `docker-compose.example.yml:64` — jamais dans le
    `docker-compose.yml` réel, qui est **gitignoré**. Le correctif était donc écrit,
    commité, gardé… et appliqué à rien.

    C'est la forme la plus coûteuse d'un garde : il ne ment pas, il regarde ailleurs.
    `test_the_running_scheduler_agrees_with_the_template` ci-dessous interroge le
    système qui tourne, et saute quand il n'y en a pas — ce qui est honnête : un test
    de CI ne peut pas juger une machine absente, mais il ne doit pas non plus laisser
    croire qu'il l'a fait.
    """
    body = COMPOSE.read_text(encoding="utf-8")
    m = re.search(r"AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL:\s*['\"]?(\d+)", body)
    assert m, (
        "MIN_FILE_PROCESS_INTERVAL is gone from the compose file. At Airflow's default "
        "of 30 s the 16 DAG files are re-parsed twice a minute, which measured as "
        "a scheduler almost always busy; at 300 s it idles at ~2 % between bursts."
    )
    assert int(m.group(1)) >= 120, (
        f"the parsing interval is back down to {m.group(1)} s. Below ~2 minutes the "
        "scheduler spends its time re-reading files that change a few times a month."
    )


def test_the_running_scheduler_agrees_with_the_template():
    """LE SYSTÈME QUI TOURNE, pas le modèle — le garde qui manquait.

    Il interroge le scheduler réel. S'il n'y en a pas (CI, poste sans Docker), il SAUTE
    plutôt que de passer : un test vert sur une machine où le sujet est absent est
    exactement ce qui a laissé ce défaut vivre.
    """
    import shutil
    import subprocess

    if not shutil.which("docker"):
        pytest.skip("docker absent — le scheduler réel n'est pas interrogeable ici")
    try:
        noms = subprocess.run(["docker", "ps", "--format", "{{.Names}}"],
                              capture_output=True, text=True, timeout=15)
    except Exception:                          # noqa: BLE001
        pytest.skip("docker injoignable")
    scheduler = next((n for n in noms.stdout.split() if "scheduler" in n), None)
    if scheduler is None:
        pytest.skip("aucun conteneur scheduler en cours")

    r = subprocess.run(
        ["docker", "exec", scheduler, "airflow", "config", "get-value",
         "scheduler", "min_file_process_interval"],
        capture_output=True, text=True, timeout=60)
    valeurs = [x for x in r.stdout.split() if x.isdigit()]
    if not valeurs:
        pytest.skip(f"réponse illisible du scheduler : {r.stdout[:120]!r}")
    effectif = int(valeurs[-1])

    body = COMPOSE.read_text(encoding="utf-8")
    m = re.search(r"AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL:\s*['\"]?(\d+)", body)
    attendu = int(m.group(1)) if m else 0
    assert effectif >= 120, (
        f"le scheduler qui TOURNE reparse toutes les {effectif} s, alors que le gabarit "
        f"déclare {attendu} s. Le réglage vit dans `docker-compose.example.yml` et le "
        "fichier réellement utilisé — `docker-compose.yml`, gitignoré — ne le porte pas.\n"
        "Ajouter `AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL: '300'` à l'ancrage "
        "`&airflow-common-env`, puis `docker-compose up -d airflow-scheduler`.")


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
