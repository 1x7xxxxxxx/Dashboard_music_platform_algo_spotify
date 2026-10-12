"""The state of the last test verdict against the last code edit — ONE definition (R549).

Type: Utility
Uses: subprocess (git), pathlib, re
Triggers: imported by .claude/hooks/require_verdict_after_edit.py (Stop gate) and
          .claude/hooks/statusline.py (the HUD, R550)
Persists in: nothing — reads `.pytest-last.started` (touched by `make test` /
             `make test-changed` at START) and `.pytest-last.log` (their `tee`)

Why a start stamp: `tee` truncates the log when the suite starts and keeps writing to
it, so the log's mtime moves DURING the run. A suite started BEFORE the last edit would
read as fresh. Only the start says which tree the verdict describes.

« Code » is a property of the file, not of its directory: a `.md`, `.yml` or `.json`
edit never makes the verdict stale, a `.py` anywhere does.

States: absent (no verdict) · périmé (code edited after the run started) · en cours ·
vert · rouge.

---
rex: []
---
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

CODE_SUFFIXES = frozenset({".py", ".sql", ".sh", ".js", ".ts"})
CODE_NAMES = frozenset({"Makefile"})
STARTED = ".pytest-last.started"
LOG = ".pytest-last.log"
_SUMMARY = re.compile(r"\b\d+ (passed|failed|errors?)\b.* in [\d.]+s")


@dataclass(frozen=True)
class Verdict:
    state: str
    passed: int = 0
    failed: int = 0
    last_edit: float | None = None
    edited_file: str | None = None


def is_code(path: str) -> bool:
    p = Path(path)
    return p.suffix in CODE_SUFFIXES or p.name in CODE_NAMES


def _git(root: Path, *args: str) -> list[str]:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                       text=True, timeout=5)
    return r.stdout.splitlines() if r.returncode == 0 else []


def _pending_files(root: Path) -> set[str]:
    """Code files not yet on the remote: uncommitted (untracked included) ∪ unpushed."""
    files = {line[3:].split(" -> ")[-1].strip('"')
             for line in _git(root, "status", "--porcelain", "--untracked-files=all")}
    files |= set(_git(root, "diff", "--name-only", "@{u}..HEAD"))
    return {f for f in files if f and is_code(f)}


def last_code_edit(root: Path) -> tuple[float, str] | None:
    """(mtime, path) of the most recently written pending code file, or None."""
    best: tuple[float, str] | None = None
    for f in _pending_files(root):
        try:
            m = (root / f).stat().st_mtime
        except OSError:
            continue  # deleted: no mtime to compare, the next edit will carry the change
        if best is None or m > best[0]:
            best = (m, f)
    return best


def _counts(summary: str) -> tuple[int, int]:
    def n(word: str) -> int:
        m = re.search(rf"(\d+) {word}", summary)
        return int(m.group(1)) if m else 0
    return n("passed"), n("failed") + n("error")


def verdict(root: Path) -> Verdict:
    edit = last_code_edit(root)
    last, file = edit if edit else (None, None)
    started, log = root / STARTED, root / LOG
    if not started.exists() and not log.exists():
        return Verdict("absent", last_edit=last, edited_file=file)
    start = started.stat().st_mtime if started.exists() else log.stat().st_mtime
    if last is not None and last > start:
        return Verdict("périmé", last_edit=last, edited_file=file)
    if not log.exists() or log.stat().st_mtime < start:
        return Verdict("en cours", last_edit=last, edited_file=file)
    lines = [ln for ln in log.read_text(errors="replace").splitlines() if _SUMMARY.search(ln)]
    if not lines:
        return Verdict("en cours", last_edit=last, edited_file=file)
    passed, failed = _counts(lines[-1])
    return Verdict("rouge" if failed else "vert", passed, failed, last, file)
