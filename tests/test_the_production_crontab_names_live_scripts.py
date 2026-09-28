"""R310 — the production crontab is versioned, and every script it runs is in the repo, executable.

Type: Test
Uses: git ls-files -s, deploy/host/crontab
Depends on: deploy/host/crontab (compared to the box by `make sync-check`)
Persists in: nothing

Five repo scripts have no other caller than the root crontab of the production box (backup,
schema drift, infra health, restore drill, Airflow cleanup). Until 2026-09-28 the repo did not
track that crontab, so an inventory could only mark them « live, unprovable ». A script the
crontab names that is renamed, archived or loses its exec bit fails at 03:00 with nobody
watching — the mail of the next check is the first sign.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRONTAB = ROOT / "deploy" / "host" / "crontab"
_SCRIPT = re.compile(r"/opt/streamlytics/(\S+?\.(?:sh|py))\b")


def scheduled_scripts(text: str) -> list[str]:
    """Repo-relative scripts named by the SCHEDULE lines (comments ignored). Pure."""
    return [m for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")
            for m in _SCRIPT.findall(line)]


def _modes() -> dict[str, str]:
    out = subprocess.run(["git", "ls-files", "-s"], cwd=ROOT, capture_output=True,
                         text=True).stdout
    return {ln.split("\t", 1)[1]: ln.split()[0] for ln in out.splitlines() if "\t" in ln}


def test_every_scheduled_script_is_tracked_and_executable() -> None:
    scripts = scheduled_scripts(CRONTAB.read_text(encoding="utf-8"))
    assert len(scripts) >= 5, f"the crontab names {len(scripts)} script(s) — the parse is off"
    modes = _modes()
    missing = [s for s in scripts if s not in modes]
    assert not missing, f"the production crontab runs scripts the repo no longer has: {missing}"
    not_exec = [s for s in scripts if modes[s] != "100755" and not _run_through_bash(s)]
    assert not not_exec, f"scheduled directly but not executable in git: {not_exec}"


def _run_through_bash(script: str) -> bool:
    """`bash /opt/…/x.sh` does not need the exec bit; a bare `/opt/…/x.sh` does."""
    return f"bash /opt/streamlytics/{script}" in CRONTAB.read_text(encoding="utf-8")


def test_the_parser_reads_schedule_lines_only_not_vacuous() -> None:
    text = ("# 0 1 * * * /opt/streamlytics/tools/ghost.sh\n"
            "0 3 * * * bash /opt/streamlytics/tools/db_backup.sh >> /var/log/x.log 2>&1\n"
            "0 4 * * * /opt/streamlytics/tools/schema_drift_cron.sh\n")
    assert scheduled_scripts(text) == ["tools/db_backup.sh", "tools/schema_drift_cron.sh"]
