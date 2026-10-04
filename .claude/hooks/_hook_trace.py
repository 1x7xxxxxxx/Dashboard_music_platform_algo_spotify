"""One line per hook run, so a SILENT hook still proves it fired (R365).

Type: Utility
Uses: os, atexit, time
Triggers: imported by every hook registered in .claude/settings.json (guard:
          tests/test_every_hook_leaves_a_trace.py)
Persists in: .claude/sessions/hook-runs-YYYYMMDD.jsonl (gitignored, pruned after 30 days)

Why: `usage_report.py` counted a hook only from the transcript attachment Claude Code
writes when a hook PRINTS something. Eight silent hooks read as « never fired » —
`pre_compact.py` among them, the night it wrote its session file.

Design (code-critic, 2026-10-04, BUILD-MODIFIED):
  * the line says THAT it ran and how long it took — no exit code: `atexit` cannot see
    it, and failures already reach the transcript because a failing hook prints;
  * one file per day, one `os.write` on an O_APPEND descriptor (atomic for a short line
    across concurrent hooks), any OSError swallowed — tracing can never break a hook;
  * traces only when the hook runs as `__main__`: a test that IMPORTS a hook writes
    nothing, and under pytest a hook SUBPROCESS writes only to an explicit
    HOOK_TRACE_DIR (the R363 class: tests polluting the real measurement journals).

Limit: a hook that dies before reaching this import (syntax error) still reads as 0.

---
rex: []
---
"""
from __future__ import annotations

import atexit
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

KEEP_DAYS = 30
_DEFAULT_DIR = Path(__file__).resolve().parents[1] / "sessions"


def trace_dir() -> Path | None:
    """Where to write, or None when a test did not name a directory."""
    explicit = os.environ.get("HOOK_TRACE_DIR")
    if explicit:
        return Path(explicit)
    if "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules:
        return None
    return _DEFAULT_DIR


def _write(directory: Path, hook: str, started: float) -> None:
    now = datetime.now(timezone.utc)
    line = json.dumps({"hook": hook, "ts": now.isoformat(timespec="milliseconds"),
                       "ms": int((time.monotonic() - started) * 1000)}) + "\n"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        fd = os.open(directory / f"hook-runs-{now:%Y%m%d}.jsonl",
                     os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
        _prune(directory, now)
    except OSError:
        pass


def _prune(directory: Path, now: datetime) -> None:
    cutoff = f"hook-runs-{now - timedelta(days=KEEP_DAYS):%Y%m%d}.jsonl"
    for old in directory.glob("hook-runs-*.jsonl"):
        if old.name < cutoff:
            old.unlink(missing_ok=True)


def trace(hook_file: str) -> None:
    """Register the run of `hook_file`; a no-op unless it is the running script."""
    main = getattr(sys.modules.get("__main__"), "__file__", None)
    if not main or Path(main).resolve() != Path(hook_file).resolve():
        return
    directory = trace_dir()
    if directory is None:
        return
    rel = Path(hook_file).resolve()
    name = f"{rel.parent.name}/{rel.name}"
    atexit.register(_write, directory, f".claude/{name}", time.monotonic())
