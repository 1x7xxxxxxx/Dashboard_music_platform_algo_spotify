"""A heavy target leaves a memory trace that a crash cannot take with it.

Type: Sub
Uses: tools/dev/mem_trace.py, Makefile (`make -n`)
Depends on: nothing — a scratch log, a `sleep` as the watched process

R330 (2026-09-29): WSL froze mid-suite with the error-management probe running beside it,
and no kernel log survived the restart. The trace is the only record the next freeze will
leave, so what is pinned here is what a freeze tests: lines already on disk when the
tracer is killed hard, and every lock-holding target starting it.

Mutation record (2026-09-29): seen red with `append` buffering in memory until « fin »
(kill -9 ⇒ nothing on disk), and with `$(TRACE_MEMORY)` removed from HOLD_HEAVY_LOCK.
Not covered: the fsync itself — a process kill leaves the page cache intact, only a VM
that dies takes it, and no test here can kill the VM.
"""
import importlib.util
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_TOOL = ROOT / "tools/dev/mem_trace.py"
_spec = importlib.util.spec_from_file_location("mem_trace", _TOOL)
mt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mt)


def test_a_line_says_what_held_the_memory() -> None:
    mem = mt.meminfo("MemAvailable:   2048000 kB\nSwapTotal: 4194304 kB\nSwapFree: 3145728 kB\n")
    out = mt.line("test", mem, [("python", 700), ("claude", 400)], "questdb=6GiB / 8GiB")
    assert "avail=2000Mo" in out and "swap=1024Mo" in out
    assert "python:700" in out and "questdb=6GiB" in out and out.endswith("\n")


def test_the_trace_stops_with_the_job_and_says_so(tmp_path) -> None:
    watched = subprocess.Popen(["sleep", "0.6"])
    log = tmp_path / "trace.log"
    mt.run("job", watched.pid, every=0.2, log=log)
    watched.wait()
    lines = log.read_text().splitlines()
    assert len(lines) >= 2 and lines[-1].endswith("[job] fin"), lines
    assert all("avail=" in ln for ln in lines[:-1])


def test_lines_survive_a_hard_kill_of_the_tracer(tmp_path) -> None:
    """The freeze case: the process dies without a chance to flush anything."""
    log = tmp_path / "trace.log"
    code = (f"import importlib.util,sys;s=importlib.util.spec_from_file_location('m','{_TOOL}');"
            f"m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
            f"from pathlib import Path;m.run('k',{1},0.1,log=Path('{log}'))")
    tracer = subprocess.Popen([sys.executable, "-c", code])
    deadline = time.time() + 20
    while time.time() < deadline and not (log.exists() and log.read_text().count("\n") >= 2):
        time.sleep(0.1)
    tracer.send_signal(signal.SIGKILL)
    tracer.wait()
    assert log.read_text().count("avail=") >= 2, "a hard kill lost what was already sampled"


def test_every_target_holding_the_heavy_lock_starts_the_tracer() -> None:
    for target in ("test", "test-changed", "test-fast"):
        dry = subprocess.run(["make", "-n", target], cwd=ROOT, capture_output=True,
                             text=True, timeout=60).stdout
        assert "heavy-memory.lock" in dry, f"{target} no longer holds the lock"
        assert f'mem_trace.py --label "{target}"' in dry and "9>&-" in dry, (
            f"`make {target}` runs without a memory trace, or hands it the lock")
