#!/usr/bin/env python3
"""Who holds ~/.cache/heavy-memory.lock, and should a new heavy job wait for it?

Type: Utility
Uses: /proc/<pid>/fd, /proc/<pid>/cmdline; fcntl.flock (for Python callers)
Triggers: tools/dev/heavy_lock.bash (the test targets), tools/dev/probe_error_management.py
Persists in: nothing — prints `wait`, `proceed` or `free`, and the holder, on stdout

R331 (2026-09-29). WSL froze while `make test-changed` ran BESIDE the error-management
probe: the test targets took the lock with `flock -n` and ran anyway when it was held
(« ingestion en cours, réserve élargie »), and the probe did not take it at all.

The holder is read from /proc, not from a label written in the file: the knowledge-rag
ingestion cron holds the lock without writing anything, so a label would be stale
exactly when it matters (code-critic R331 proposed labels; /proc needs no cooperation).
An ingestion is visible to `pytest_workers.py`, which widens its reserve — running beside
it stays allowed, as before. Another suite or the probe is NOT visible to that snapshot
and grows during the run: those are waited for.
"""
from __future__ import annotations

import fcntl
import os
import sys
import time
from pathlib import Path

LOCK = Path.home() / ".cache" / "heavy-memory.lock"
_INGEST = ("ingest", "book_drop", "rag-mail")


def _ancestors(proc: Path = Path("/proc")) -> set[int]:
    pids, pid = set(), os.getpid()
    while pid > 1 and pid not in pids:
        pids.add(pid)
        try:
            pid = int((proc / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return pids


def holders(lock: Path = LOCK, proc: Path = Path("/proc")) -> list[str]:
    """Command lines of the processes that have the lock file open (ours excluded)."""
    # The asker and its shells have the file open too (the Makefile opens fd 9, then asks
    # from a `$(…)` subshell that inherits it): every ancestor is « us ».
    target, us, out = str(lock), _ancestors(proc), []
    for d in proc.iterdir():
        if not d.name.isdigit() or int(d.name) in us:
            continue
        try:
            fds = list((d / "fd").iterdir())
            if not any(os.readlink(f) == target for f in fds):
                continue
            argv = (d / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        out.append(argv.strip())
    return out


def decide(cmdlines: list[str]) -> str:
    """`free` (nobody), `proceed` (only an ingestion — the reserve sees it), else `wait`. Pure."""
    if not cmdlines:
        return "free"
    if all(any(k in c for k in _INGEST) for c in cmdlines):
        return "proceed"
    return "wait"


def acquire(label: str, wait_s: float, lock: Path = LOCK) -> "int | None":
    """For Python heavy jobs: hold the lock (fd returned, non-inheritable) or None on timeout.

    An ingestion holding it is not waited for — same rule as the test targets.
    """
    lock.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o644)
    deadline = time.monotonic() + wait_s
    said = False
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            who = holders(lock)
            if decide(who) == "proceed":
                return fd
            if time.monotonic() >= deadline:
                os.close(fd)
                return None
            if not said:
                print(f"⏳ {label} : un travail lourd tient {lock.name} — attente "
                      f"(≤ {int(wait_s)} s) : {'; '.join(w[:100] for w in who) or '?'}",
                      file=sys.stderr)
                said = True
            time.sleep(2)


def main() -> int:
    who = holders()
    print(decide(who))
    for w in who:
        print(f"  {w[:160]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
