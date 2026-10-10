"""Each shell signature below goes RED on its own defect, fabricated in a scratch directory.

Type: Sub
Uses: .claude/dev-docs/error-classes.md (the `- signature:` of each class named here)
Depends on: bash, GNU grep — the signatures run through `bash -c`, never through this
workstation's interactive shell, whose `grep` an RTK hook rewrites

R325 (2026-09-29). R324 dated these by hand; two of them turned out to have been unable to go
red for months (`make-fail-late`: `\\t` is not a TAB for `grep -E`; `operator-guidance…`:
a file that became a package, grep exit 2 read as green by `!`). A date proves the signature
went red ONCE. This proves it on every run, against the signature AS WRITTEN in the catalogue
— reword it wrongly and the fabricated defect stops being seen here.

Mutation record (2026-09-29): seen red with `make-fail-late`'s `[[:space:]]+` put back to
`\\t`, and with `operator-guidance…`'s `credentials/` put back to `credentials.py`.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.catalogue_source import signatures

ROOT = Path(__file__).resolve().parents[1]
_BROKEN_CODES = {2, 5, 126, 127}   # audit_runner._BROKEN_CODES — exits that are not a verdict


def _signature(cid: str) -> str:
    return signatures()[cid]


def _write(root: Path, rel: str, content: str) -> None:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(content, encoding="utf-8")


def _copy(root: Path, rel: str) -> None:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / rel, root / rel)


def _fab_make_fail_late(t: Path) -> None:
    _write(t, "Makefile", "up:\n\tdocker-compose up -d\n")


def _fab_repo_copy(t: Path) -> None:
    _write(t, "Makefile", "sync-check:\n\t@echo no drift step here\n")


def _fab_measurement(t: Path) -> None:
    _write(t, ".claude/dev-docs/test-suite-performance.md", "# perf\nrien sur la charge\n")


def _fab_mixed_date(t: Path) -> None:
    _write(t, "src/dashboard/views/x.py", 'd = sorted(df["date"].unique())\n')


def _fab_naive_now(t: Path) -> None:
    _write(t, "src/y.py", 'from datetime import datetime\nrow = {"at": datetime.now()}\n')


def _fab_tz_mix(t: Path) -> None:
    _write(t, "src/dashboard/views/w.py", 'import pandas as pd\ns = pd.to_datetime(df["d"])\n')


def _fab_operator(t: Path) -> None:
    for rel in ("src/utils/alert_root_cause.py", "src/dashboard/views/useful_links.py"):
        _copy(t, rel)
    for guide in (ROOT / ".claude/dev-docs").glob("*guide*.md"):
        _copy(t, str(guide.relative_to(ROOT)))
    _write(t, "src/dashboard/views/credentials/_x.py", 'M = "lancez spotify_auth.py"\n')


def _fab_merged_branch(t: Path) -> None:
    _write(t, "bin/gh", "#!/bin/sh\necho false\n")
    (t / "bin/gh").chmod(0o755)


CASES = {
    "make-fail-late": _fab_make_fail_late,
    "repo-copy-of-a-config-is-not-what-runs": _fab_repo_copy,
    "a-measurement-taken-under-self-inflicted-load": _fab_measurement,
    "mixed-date-timestamp": _fab_mixed_date,
    "naive-datetime-now": _fab_naive_now,
    "tz-aware-naive-mix": _fab_tz_mix,
    "operator-guidance-phantom-or-wrong-auth": _fab_operator,
    "a-merged-branch-outlives-its-pull-request": _fab_merged_branch,
}


def _run(sig: str, cwd: Path) -> int:
    return _run_full(sig, cwd).returncode


def _run_full(sig: str, cwd: Path) -> subprocess.CompletedProcess:
    env = {"PATH": f"{cwd / 'bin'}:/usr/bin:/bin", "HOME": str(cwd), "GITHUB_REPOSITORY": ""}
    return subprocess.run(["bash", "-c", sig], cwd=cwd, capture_output=True, text=True,
                          timeout=60, env=env)


def _healthy(cid: str, t: Path) -> None:
    """The same directory WITHOUT the defect: the signature must be green here first, or its
    red on the fabricated defect would prove nothing."""
    if cid == "a-merged-branch-outlives-its-pull-request":
        _write(t, "bin/gh", "#!/bin/sh\necho true\n")
        (t / "bin/gh").chmod(0o755)
    elif cid in ("repo-copy-of-a-config-is-not-what-runs",):
        _copy(t, "Makefile")
    elif cid == "a-measurement-taken-under-self-inflicted-load":
        _copy(t, ".claude/dev-docs/test-suite-performance.md")
    elif cid == "operator-guidance-phantom-or-wrong-auth":
        _fab_operator(t)
        (t / "src/dashboard/views/credentials/_x.py").write_text("M = 1\n")


@pytest.mark.parametrize("cid", sorted(CASES))
def test_the_detector_sees_the_defect_it_is_written_for(cid: str, tmp_path: Path) -> None:
    sig = _signature(cid)
    _healthy(cid, tmp_path)
    assert _run(sig, tmp_path) == 0, f"{cid}: red WITHOUT its defect — it proves nothing"
    CASES[cid](tmp_path)
    red = _run_full(sig, tmp_path)
    assert red.returncode != 0, f"{cid}: its signature stays green on its own defect"
    # R495 — a red that is a CRASH (grep exit 2 on a missing file, command not found 127,
    # a Python traceback) is not the signature seeing its defect.
    out = red.stdout + red.stderr
    assert red.returncode not in _BROKEN_CODES and "Traceback (most recent call last)" not in out, (
        f"{cid}: exit {red.returncode} is a crash, not a verdict on the defect:\n{out[-1500:]}")
