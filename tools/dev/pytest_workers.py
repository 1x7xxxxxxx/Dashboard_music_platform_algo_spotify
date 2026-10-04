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
    each knowledge-rag server, up to its measured peak         +(2 300 − its RSS) Mo
    n8n-ollama up, or an ingestion process running             +3 600 Mo
    swap below 1 Go free                                       +the deficit

An ingestion that STARTS during the suite cannot be seen by this snapshot. That case is
closed by exclusion, not detection: the test targets hold `~/.cache/heavy-memory.lock`,
and the hourly ingestion crons skip their run while it is held.

R352 (2026-10-04): the knowledge-rag figure was 1 600 Mo and wrong by 2.5×. VS Code Remote
dropped three times during a `make test-changed` at 2 workers; `~/.cache/mem-trace.log`
shows two `python3` processes at 3,2–4,0 Go next to workers at ~250 Mo, with swap full.
A first `search_books` took the server from 113 Mo to 2 228 Mo (VmHWM, measured that day),
the only peak ever MEASURED for it. A first version of this fix reserved 4 100 Mo, from a
`python3:4049` line of the trace inferred to be a RAG server: it was the error-class-health
replay (VmHWM 4 047 Mo measured once streamed, R352), run inside an xdist worker by
`generated_cache` — the trace shows workers at 4 025-4 078 Mo since 2026-09-29. A server
whose model is ALREADY loaded can still grow, so it reserves the rest of the way to the
peak instead of nothing. Swap is counted too: MemAvailable says nothing about a swap that
is already full, and that is when the kernel starts failing contiguous allocations.

The worker count cannot make the machine safe by itself — at the floor of 2 it still
froze. The suite is ALSO run in a capped systemd scope (Makefile `SUITE_SCOPE`).

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
RAG_PEAK_MB = 2300
SWAP_FLOOR_MB = 1024
HEAVY_MB = 3600
PER_WORKER_MB = 700
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


def workers(mem_available_mb: int, procs: list[Proc], ollama_up: bool, ncpu: int,
            swap_free_mb: int = SWAP_FLOOR_MB) -> tuple[int, str]:
    """(worker count, why) for the memory available NOW and what can still grow."""
    reserve, why = BASE_MB, [f"base {BASE_MB}"]
    rag = [p for p in procs if _is_rag_server(p)]
    rag_growth = sum(max(0, RAG_PEAK_MB - p.rss_mb) for p in rag)
    if rag_growth:
        reserve += rag_growth
        why.append(f"{len(rag)} knowledge-rag jusqu'à leur pic {RAG_PEAK_MB} +{rag_growth}")
    if swap_free_mb < SWAP_FLOOR_MB:
        reserve += SWAP_FLOOR_MB - swap_free_mb
        why.append(f"swap libre {swap_free_mb} Mo +{SWAP_FLOOR_MB - swap_free_mb}")
    ingest = any(_is_ingestion(p) for p in procs)
    if ollama_up or ingest:
        reserve += HEAVY_MB
        why.append(f"{'n8n-ollama' if ollama_up else 'ingestion'} en cours +{HEAVY_MB}")
    n = max(2, min(ncpu, (mem_available_mb - reserve) // PER_WORKER_MB))
    return n, (f"{n} workers — MemAvailable {mem_available_mb} Mo, réserve {reserve} "
               f"({' · '.join(why)}), {PER_WORKER_MB} Mo/worker, borné à [2, {ncpu}]")


def _meminfo_mb(key: str, default: int) -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith(f"{key}:"):
            return int(line.split()[1]) // 1024
    return default


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
    swap_free = (_meminfo_mb("SwapFree", SWAP_FLOOR_MB)
                 if _meminfo_mb("SwapTotal", 0) else SWAP_FLOOR_MB)
    n, why = workers(_meminfo_mb("MemAvailable", 4096), _processes(), _ollama_up(),
                     os.cpu_count() or 4, swap_free)
    print(why, file=sys.stderr)
    print(n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
