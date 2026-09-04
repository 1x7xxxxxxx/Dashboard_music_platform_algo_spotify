"""Guard: a backup exists somewhere other than the disk it protects, and is proven.

Type: Utility
Uses: ast, pathlib
Triggers: pytest
Persists in: nothing

Error class `backup-shares-the-fate-of-what-it-protects`.

Measured on the production host, 2026-09-03:

* **21 daily archives, all under `/opt/streamlytics/backups` on `/dev/sda1`** — the
  same disk as the database they back up. `crontab -l` contained no `rsync`, no `s3`,
  no `rclone`. If that disk is lost, the backups go with it.
* **`tools/db_restore_test.sh` existed and had no scheduled caller.** Three crons ran
  (backup 03:00, schema drift 04:00, infra health 05:00); none restored anything.

And the drill itself did not prove what its name claims. It asserted `TABLES >= 1` and
merely PRINTED a row count without comparing it to anything, so a dump truncated to its
first table, or a schema-only `pg_dump`, passed green. It was a `gunzip` check wearing a
backup check's name.

## The three things this pins

1. `db_backup.sh` pushes offsite, and **says so loudly when it cannot** — but still
   exits 0, because the local backup did succeed and turning it red would make it
   indistinguishable from a broken `pg_dump`. The refusal to be silent lives in
   `alert_monitor.check_offsite_backup` instead, every night.
2. The drill **compares** the restored database to the live one, with an exact count —
   not `pg_stat_user_tables.n_live_tup`, which is an estimate refreshed by ANALYZE and
   was measured stale: the first version of the comparison reported "40 015 restored
   vs 1 149 live" **on the same database**.
3. The 10 % row tolerance is calibrated on the measured growth (2 736 rows/day against
   ~49 000 in base ≈ 5,6 %/day), not on a round number.
"""
from __future__ import annotations

import ast
from pathlib import Path


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


REPO = _repo_root()
BACKUP = REPO / "tools" / "db_backup.sh"
DRILL = REPO / "tools" / "db_restore_test.sh"
MONITOR = REPO / "airflow" / "dags" / "alert_monitor.py"


def test_the_backup_script_pushes_offsite():
    body = BACKUP.read_text(encoding="utf-8")
    assert "R2_REMOTE" in body, (
        "db_backup.sh no longer references R2_REMOTE: the archive stays on the disk "
        "it protects, which is the defect this guard exists for."
    )
    assert "rclone copy" in body, "no offsite copy command in db_backup.sh"


def test_a_missing_offsite_target_is_loud_but_does_not_break_the_local_backup():
    """Both halves matter, and they pull in opposite directions.

    Silent would hide the gap; fatal would turn a working local backup red and make
    it indistinguishable from a broken pg_dump.
    """
    lines = BACKUP.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if 'if [ -z "${R2_REMOTE:-}" ]' in ln)
    # Sliced LINE by line, not by `index("fi")`: that substring matches the "fi" inside
    # the French word « défini » two lines below, and truncated the branch before its
    # own redirections. Third time today a substring predicate answered a question
    # about structure.
    end = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == "fi")
    branch = "\n".join(lines[start:end])
    assert ">&2" in branch, "the missing-offsite warning does not go to stderr"
    assert "exit 0" in branch, (
        "the missing-offsite branch aborts the script. The local backup succeeded; "
        "failing here would report a working backup as broken."
    )


def test_the_monitor_reports_a_missing_or_stale_offsite_copy():
    """The half that makes the gap impossible to ignore."""
    tree = ast.parse(MONITOR.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "check_offsite_backup"),
              None)
    assert fn is not None, (
        "check_offsite_backup is gone from alert_monitor. db_backup.sh deliberately "
        "stays green without an offsite target, so nothing else says it."
    )
    states = {n.value for n in ast.walk(fn)
              if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    for expected in ("absent", "stale", "empty", "unreadable"):
        assert expected in states, (
            f"the check no longer distinguishes the '{expected}' case. 'I cannot read "
            "the remote' and 'the remote is empty' need different gestures."
        )


def test_the_monitor_renders_the_finding_in_the_mail():
    """A detector whose finding never reaches the mail is a detector nobody reads."""
    body = MONITOR.read_text(encoding="utf-8")
    assert "offsite_backup" in body and "Sauvegarde hors-site" in body, (
        "the offsite finding is computed but never rendered into the consolidated "
        "alert — the exact shape of `detector-written-and-never-called`."
    )


def test_the_drill_compares_the_restore_to_the_live_database():
    raw = DRILL.read_text(encoding="utf-8")
    # Comment lines stripped: this file explains at length WHY `n_live_tup` is the
    # wrong source, and a check reading the whole text fires on its own reasoning.
    body = "\n".join(ln for ln in raw.splitlines() if not ln.lstrip().startswith("#"))
    assert "LIVE_ROWS" in body and "MIN_ROWS" in body, (
        "the restore drill no longer compares row counts against the live database. "
        "Asserting only 'tables >= 1' passes on a schema-only dump."
    )
    assert "n_live_tup" not in body, (
        "the drill counts rows via pg_stat_user_tables, which is an ESTIMATE "
        "refreshed by ANALYZE. Measured 2026-09-04: it reported 40 015 restored vs "
        "1 149 live on the same database."
    )
    assert "query_to_xml" in body, "the drill no longer counts rows exactly"


def test_the_monitor_does_not_shell_out_to_a_binary_its_image_lacks():
    """Error class `check-calls-a-binary-its-image-lacks`.

    Measured 2026-09-04 inside `airflow_scheduler`: `command -v rclone` and
    `command -v git` both return nothing. The first version of this check ran
    `subprocess.run(['rclone', 'lsjson', ...])` from an Airflow task, so it would have
    answered `unreadable` every single night — including after R2 was correctly
    configured on the host. A check that can never go green is not a check.

    The probe belongs where the credentials and the binaries are (the host script);
    the task reads the receipt that probe leaves behind.
    """
    tree = ast.parse(MONITOR.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "check_offsite_backup")
    forbidden = {"rclone", "git", "docker", "psql", "gpg"}
    for node in ast.walk(fn):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value not in forbidden, (
                f"check_offsite_backup names the host binary {node.value!r}. It runs "
                "inside the Airflow image, which has none of them."
            )


def test_the_receipt_is_the_single_contract_between_the_two_halves():
    """The host writes it, the container reads it — a rename on one side is silent."""
    backup = BACKUP.read_text(encoding="utf-8")
    monitor = MONITOR.read_text(encoding="utf-8")
    assert "offsite_receipt.json" in backup and "offsite_receipt.json" in monitor, (
        "the receipt path diverged between db_backup.sh and alert_monitor: the "
        "monitor would read a file nobody writes and report 'absent' for ever."
    )
    for key in ("archives", "verified_at", "target"):
        assert f'"{key}"' in backup, f"db_backup.sh no longer writes {key!r}"
        assert f"'{key}'" in monitor or f'"{key}"' in monitor, (
            f"alert_monitor no longer reads {key!r} from the receipt")


def test_the_git_target_encrypts_before_it_pushes():
    """The archive leaves the machine encrypted, or it does not leave.

    The git target is a third-party host (ADR-015). What makes it acceptable is not
    the repo being private — it is that the bytes are AES256 before they move.
    """
    body = BACKUP.read_text(encoding="utf-8")
    enc = body.index("--cipher-algo AES256")
    push = body.index("push -q --force origin backups")
    assert enc < push, "the push happens before the encryption"
    assert "*.sql.gz.gpg" in body, (
        "the offsite work tree no longer selects the ENCRYPTED archives — a glob "
        "widened to *.sql.gz would publish the dumps in clear."
    )


def test_the_offsite_push_is_verified_by_reading_the_remote_back():
    """The receipt attests a presence, not an intention."""
    body = BACKUP.read_text(encoding="utf-8")
    assert "ls-remote origin refs/heads/backups" in body, (
        "nothing reads the remote back after the git push: the receipt would be "
        "written on the strength of a zero exit code alone."
    )
    assert 'LOCAL_SHA" != "$REMOTE_SHA' in body, "the two SHAs are no longer compared"
