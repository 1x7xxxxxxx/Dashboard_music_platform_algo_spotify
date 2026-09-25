#!/usr/bin/env python3
"""How many pytest workers this workstation can afford right now.

Type: Utility
Uses: /proc/meminfo, /proc/<pid>/{cmdline,status}, `docker ps` (optional), os.cpu_count
Triggers: Makefile (`PYTEST_WORKERS`)
Persists in: nothing — prints one integer on stdout, the reasoning on stderr

Why a reserve that depends on what is running
---------------------------------------------
Until 2026-09-25 the Makefile computed `(MemAvailable − 5120) / 700` in shell. The fixed
5 120 Mo was set on 2026-09-17 after three OOM kills in a day, when two services could
GROW by gigabytes in the middle of a suite: `n8n-ollama` (a resident model, 2,5 Go) and
the `knowledge-rag` MCP server (1,5 Go preloaded in every session). On this 10 Go WSL
it pinned `make test` at 2 workers for good.

Both changed that day: n8n runs on Sundays only, and knowledge-rag loads its model at
the first search and drops it after 10 idle minutes. What is ALREADY resident is already
out of `MemAvailable`; the reserve only has to cover what can still grow:

    base margin (VS Code, Claude sessions, page cache)          1 536 Mo, always
    each knowledge-rag server whose model is not loaded        +1 600 Mo
    n8n-ollama up, or an ingestion process running             +3 600 Mo

An ingestion that STARTS during the suite cannot be seen by this snapshot. That case is
closed by exclusion, not detection: the test targets hold `~/.cache/heavy-memory.lock`,
and the hourly ingestion crons skip their run while it is held.

The 700 Mo divisor is unchanged: measured worker peaks (VmHWM, full suite, -n 3) are
573 · 414 · 411 Mo.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

BASE_MB = 1536
RAG_UNLOADED_MB = 1600
HEAVY_MB = 3600
PER_WORKER_MB = 700
RAG_LOADED_RSS_MB = 800
_INGEST_SCRIPTS = ("ingest.py", "ingest_drop.py", "mail_ingest.py")


class Proc(NamedTuple):
    argv: list[str]
    rss_mb: int
    cwd: str


def _is_python(argv: list[str]) -> bool:
    return bool(argv) and Path(argv[0]).name.startswith("python")


def _is_rag_server(p: Proc) -> bool:
    """The Python process serving knowledge-rag — not its `uv run` wrapper, not a shell
    whose command line merely MENTIONS the path (both matched a text search here)."""
    return (_is_python(p.argv) and any(Path(a).name == "server.py" for a in p.argv[1:])
            and ("knowledge-rag" in p.cwd or "knowledge-rag" in p.argv[0]))


def _is_ingestion(p: Proc) -> bool:
    return _is_python(p.argv) and any(Path(a).name in _INGEST_SCRIPTS for a in p.argv[1:])


def workers(mem_available_mb: int, procs: list[Proc],
            ollama_up: bool, ncpu: int) -> tuple[int, str]:
    """(worker count, why) for the memory available NOW and what can still grow."""
    reserve, why = BASE_MB, [f"base {BASE_MB}"]
    rag = [p for p in procs if _is_rag_server(p) and p.rss_mb < RAG_LOADED_RSS_MB]
    if rag:
        reserve += RAG_UNLOADED_MB * len(rag)
        why.append(f"{len(rag)} knowledge-rag sans modèle chargé +{RAG_UNLOADED_MB * len(rag)}")
    ingest = any(_is_ingestion(p) for p in procs)
    if ollama_up or ingest:
        reserve += HEAVY_MB
        why.append(f"{'n8n-ollama' if ollama_up else 'ingestion'} en cours +{HEAVY_MB}")
    n = max(2, min(ncpu, (mem_available_mb - reserve) // PER_WORKER_MB))
    return n, (f"{n} workers — MemAvailable {mem_available_mb} Mo, réserve {reserve} "
               f"({' · '.join(why)}), {PER_WORKER_MB} Mo/worker, borné à [2, {ncpu}]")


def _mem_available_mb() -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) // 1024
    return 4096


def _processes() -> list[Proc]:
    out = []
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            argv = [a.decode(errors="replace")
                    for a in (d / "cmdline").read_bytes().split(b"\0") if a]
            rss = next((int(ln.split()[1]) // 1024 for ln in (d / "status").read_text()
                        .splitlines() if ln.startswith("VmRSS:")), 0)
            cwd = os.readlink(d / "cwd")
        except OSError:
            continue
        if argv:
            out.append(Proc(argv, rss, cwd))
    return out


def _ollama_up() -> bool:
    try:
        r = subprocess.run(["docker", "ps", "--filter", "name=n8n-ollama", "--format",
                            "{{.Names}}"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return "n8n-ollama" in r.stdout


def main() -> int:
    n, why = workers(_mem_available_mb(), _processes(), _ollama_up(), os.cpu_count() or 4)
    print(why, file=sys.stderr)
    print(n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
