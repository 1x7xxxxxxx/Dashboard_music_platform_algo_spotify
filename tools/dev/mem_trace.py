#!/usr/bin/env python3
"""Sample the workstation's memory while a heavy job runs, into a file that survives a crash.

Type: Utility
Uses: /proc/meminfo, /proc/<pid>/{comm,status}, `docker stats` (optional, 5 s timeout)
Triggers: Makefile (`TRACE_MEMORY`, held by the test targets), tools/dev/probe_error_management.py
Persists in: ~/.cache/mem-trace.log (rotated to .1 past 1 MB) — on the ext4 disk, NOT /tmp

R330 (2026-09-29). WSL froze at 01:28:46 that night: every writer went silent in the same
second (`.pytest-last.log` at 45 %, the VS Code server's git log) while a full-size
`make test-changed` ran BESIDE the error-management probe, with another project's QuestDB
container up. The owner restarted Windows eleven minutes later, and WSL keeps no kernel log
across a restart: the cause could only be INFERRED. This tracer writes one line every
`--every` seconds — MemAvailable, swap used, the five largest resident processes, the
containers' usage — with an fsync, so the last line before the next freeze says what held
the memory. It stops by itself when the watched process exits.

Read it: `tail -20 ~/.cache/mem-trace.log`.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

LOG = Path.home() / ".cache" / "mem-trace.log"
ROTATE_BYTES = 1_000_000
TOP = 5


def meminfo(text: str) -> dict[str, int]:
    """{field: Mo} from /proc/meminfo's text. Pure."""
    out = {}
    for line in text.splitlines():
        name, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            out[name] = int(parts[0]) // 1024
    return out


def top_rss(proc: Path = Path("/proc"), n: int = TOP) -> list[tuple[str, int]]:
    """The n largest resident processes as (name, Mo), largest first."""
    found = []
    for d in proc.iterdir():
        if not d.name.isdigit():
            continue
        try:
            rss = next((int(ln.split()[1]) // 1024 for ln in (d / "status").read_text()
                        .splitlines() if ln.startswith("VmRSS:")), 0)
            name = (d / "comm").read_text().strip()
        except (OSError, ValueError):
            continue
        found.append((name, rss))
    return sorted(found, key=lambda x: -x[1])[:n]


def containers() -> str:
    """`name usage` per running container, or why it is unknown — never an empty « none »."""
    try:
        r = subprocess.run(["docker", "stats", "--no-stream", "--format",
                            "{{.Name}}={{.MemUsage}}"], capture_output=True, text=True,
                           timeout=5)
    except (OSError, subprocess.SubprocessError) as e:
        return f"docker ? ({type(e).__name__})"
    if r.returncode != 0:
        return "docker ? (rc≠0)"
    return " ".join(r.stdout.split()) or "aucun conteneur"


def line(label: str, mem: dict[str, int], top: list[tuple[str, int]], ctr: str) -> str:
    """One trace line. Pure."""
    swap = mem.get("SwapTotal", 0) - mem.get("SwapFree", 0)
    procs = " ".join(f"{n}:{m}" for n, m in top)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return (f"{now} [{label}] avail={mem.get('MemAvailable', -1)}Mo swap={swap}Mo "
            f"| {procs} | {ctr}\n")


def append(text: str, log: Path = LOG) -> None:
    """Append and fsync: a line buffered in memory is exactly what a freeze loses."""
    log.parent.mkdir(parents=True, exist_ok=True)
    if log.exists() and log.stat().st_size > ROTATE_BYTES:
        log.replace(log.with_suffix(".log.1"))
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())


def alive(pid: int, proc: Path = Path("/proc")) -> bool:
    """Running, not merely present: a zombie answers `kill(pid, 0)` until it is reaped."""
    try:
        stat = (proc / str(pid) / "stat").read_text()
    except OSError:
        return False
    return stat.rsplit(")", 1)[-1].split()[0] not in ("Z", "X")


def run(label: str, watch: int, every: float, log: Path = LOG, samples: int = 0) -> int:
    """Sample until `watch` exits (or `samples` lines were written, for tests)."""
    written = 0
    while alive(watch):
        mem = meminfo(Path("/proc/meminfo").read_text())
        append(line(label, mem, top_rss(), containers()), log)
        written += 1
        if samples and written >= samples:
            break
        time.sleep(every)
    append(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} [{label}] fin\n", log)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--label", default="job")
    ap.add_argument("--watch", type=int, default=os.getppid(),
                    help="pid dont la fin arrête la trace (défaut : le parent)")
    ap.add_argument("--every", type=float, default=15.0)
    args = ap.parse_args()
    try:
        return run(args.label, args.watch, args.every)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
