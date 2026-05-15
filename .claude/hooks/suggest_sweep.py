#!/usr/bin/env python3
"""
Stop hook — suggests running /sweep when the session looks like a bug fix.

Detects a "bugfix-shaped" session via four signals (fires if ANY is true) and
prints ONE actionable line to stderr pointing at /sweep. It never runs the
sweep, never blocks, exits 0 on any error. Mirrors the contract of draft_rex.py
(session-window + observations helpers replicated, not imported — hooks run
standalone). Position in the Stop chain: AFTER draft_rex.py (signal 4 needs
pending-rex.md populated first), BEFORE draft_devlog.py.

---
rex: []
---
"""
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_SESSION_MARKER_FILE = ".claude/sessions/.session-start-ts"
_PENDING_REX = ".claude/sessions/pending-rex.md"
_CATALOGUE = ".claude/dev-docs/error-classes.md"
_FALLBACK_WINDOW_SEC = 2 * 60 * 60  # 2h
_FIX_RE = re.compile(r"\b(fix|bug|hotfix|regression|broke|broken|crash)\b", re.I)
_RISK_DIRS = ("src/collectors/", "src/dashboard/", "src/database/", "airflow/dags/")


def find_repo_root() -> Path:
    p = Path(os.getcwd())
    while p != p.parent:
        if (p / ".claude").exists():
            return p
        p = p.parent
    return Path(os.getcwd())


def _session_start_ts(repo_root: Path) -> float:
    marker = repo_root / _SESSION_MARKER_FILE
    if marker.exists():
        try:
            return float(marker.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            pass
    return time.time() - _FALLBACK_WINDOW_SEC


def _git(repo_root: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _fix_commits(repo_root: Path, start_ts: float) -> list[str]:
    since = datetime.fromtimestamp(start_ts, timezone.utc).isoformat()
    log = _git(repo_root, "log", f"--since={since}", "--pretty=%s")
    return [s for s in log.splitlines() if _FIX_RE.search(s)]


def _risk_py_changed(repo_root: Path) -> bool:
    names = _git(repo_root, "diff", "HEAD", "--name-only").splitlines()
    return any(
        n.endswith(".py") and not n.startswith("tests/")
        and any(n.startswith(d) for d in _RISK_DIRS)
        for n in names
    )


def _pending_rex_severe(repo_root: Path) -> bool:
    f = repo_root / _PENDING_REX
    try:
        txt = f.read_text(encoding="utf-8") if f.exists() else ""
    except OSError:
        return False
    return "severity: crit" in txt or "severity: warn" in txt


def _detect(repo_root: Path) -> tuple[str, str] | None:
    """Return (signal_name, suggested_phrase) or None."""
    start_ts = _session_start_ts(repo_root)
    commits = _fix_commits(repo_root, start_ts)
    if commits:
        return "fix-commit", commits[0][:60]
    if _pending_rex_severe(repo_root):
        return "pending-rex severity", "the issue fixed this session"
    if _risk_py_changed(repo_root):
        return "risk-dir .py change", "the change made this session"
    return None


def main() -> None:
    try:
        sys.stdin.read()
    except OSError:
        pass

    repo_root = find_repo_root()
    if not (repo_root / _CATALOGUE).exists():
        sys.exit(0)  # catalogue absent → /sweep not wired yet, stay silent

    try:
        hit = _detect(repo_root)
    except (OSError, ValueError):
        sys.exit(0)

    if hit:
        signal, phrase = hit
        print(
            f'\n🔍 Bugfix-shaped session (signal: {signal}). '
            f'Run /sweep "{phrase}" to check the whole project for this '
            f'error class and add a durable guard.',
            file=sys.stderr,
        )
    sys.exit(0)


if __name__ == "__main__":
    main()
