"""Two heavy jobs never run side by side: a suite or the probe waits for the other.

Type: Sub
Uses: tools/dev/heavy_lock.py, Makefile (HOLD_HEAVY_LOCK, via `make --eval`)
Depends on: nothing — a scratch HOME, so the real ~/.cache/heavy-memory.lock is untouched

R331 (2026-09-29): WSL froze while a full-size `make test-changed` ran beside the
error-management probe. The targets took the lock with `flock -n` and ran anyway when it
was held, and the probe did not take it. An ingestion holding it is still run beside —
`pytest_workers.py` sees it in /proc — but another suite or the probe is waited for, and
the worker count is computed AFTER the wait (code-critic R331).

Mutation record (2026-09-29): seen red with `decide` answering `proceed` for any holder,
and with the Makefile's `flock -w` replaced by the old `flock -n 9 || echo …`.
"""
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_TOOL = ROOT / "tools/dev/heavy_lock.py"
_spec = importlib.util.spec_from_file_location("heavy_lock", _TOOL)
hl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hl)


def test_only_an_ingestion_is_run_beside() -> None:
    assert hl.decide([]) == "free"
    assert hl.decide(["/bin/bash tools/run_book_drop.sh", "python ingest_drop.py"]) == "proceed"
    assert hl.decide([".venv/bin/python -m pytest -q -n 4"]) == "wait"
    assert hl.decide(["python ingest.py", "python tools/dev/probe_error_management.py"]) == "wait"


def _holder(lock: Path, tag: str) -> subprocess.Popen:
    code = ("import fcntl,os,sys,time;fd=os.open(sys.argv[1],os.O_RDWR|os.O_CREAT);"
            "fcntl.flock(fd,fcntl.LOCK_EX);print('held',flush=True);time.sleep(60)")
    p = subprocess.Popen([sys.executable, "-c", code, str(lock), tag], stdout=subprocess.PIPE,
                         text=True)
    assert p.stdout.readline().strip() == "held"
    return p


def test_a_probe_waits_for_a_suite_and_runs_beside_an_ingestion(tmp_path) -> None:
    lock = tmp_path / "heavy-memory.lock"
    suite = _holder(lock, "pytest")
    try:
        assert any("pytest" in c for c in hl.holders(lock))
        t0 = time.monotonic()
        assert hl.acquire("probe", 1.0, lock) is None, "the probe ran beside a suite"
        assert time.monotonic() - t0 >= 1.0
    finally:
        suite.kill()
        suite.wait()
    fd = hl.acquire("probe", 1.0, lock)
    assert fd is not None
    os.close(fd)
    ingest = _holder(lock, "ingest_drop.py")
    try:
        fd = hl.acquire("probe", 5.0, lock)
        assert fd is not None, "an ingestion is run beside, as before"
        os.close(fd)
    finally:
        ingest.kill()
        ingest.wait()


def test_the_test_targets_wait_then_fall_back_to_two_workers(tmp_path) -> None:
    (tmp_path / ".cache").mkdir()
    lock = tmp_path / ".cache" / "heavy-memory.lock"
    suite = _holder(lock, "pytest")
    try:
        rule = "lockprobe:\n\t@bash -c '$(HOLD_HEAVY_LOCK) echo W=$$W'\n"
        t0 = time.monotonic()
        r = subprocess.run(["make", "-s", "--no-print-directory", "--eval", rule, "lockprobe",
                            "HEAVY_WAIT=1"], cwd=ROOT, capture_output=True, text=True,
                           timeout=60, env={**os.environ, "HOME": str(tmp_path)})
    finally:
        suite.kill()
        suite.wait()
    waited = time.monotonic() - t0
    # « épuisée » and the elapsed time, not « attente » nor W=2 alone: the announcement is
    # printed BEFORE the wait, and 2 is also what pytest_workers.py often computes here.
    assert "attente épuisée" in r.stdout and "W=2" in r.stdout, r.stdout + r.stderr
    assert waited >= 1.0, f"the target did not wait ({waited:.2f} s)"
