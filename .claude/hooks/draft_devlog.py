#!/usr/bin/env python3
"""
Stop hook — drafts a DEVLOG entry from this session's code modifications.

Mirrors draft_rex.py but targets real code/infra (src/, airflow/, migrations/, tests/, docs/, top-level
build files) — not Claude Code tooling. If ≥3 such files were modified this session AND no DEVLOG entry
already exists for today, writes .claude/sessions/pending-devlog.md with a fillable template + an
auto-captured context block (file list, commit shas, branch, session window). User edits the `?` slots,
sets `validated: true`, then runs `/devlog-promote` to inject into DEVLOG.md. Always exit 0 — never
blocks the Stop chain.

---
rex: []
---
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_SESSION_MARKER_FILE = ".claude/sessions/.session-start-ts"
_PENDING_FILE = ".claude/sessions/pending-devlog.md"
_DEVLOG_PATH = ".claude/dev-docs/DEVLOG.md"
_MIN_FILES = 3
_FALLBACK_WINDOW_SEC = 2 * 60 * 60  # 2h

_INCLUDE_PREFIXES = (
    "src/", "airflow/", "migrations/", "tests/", "docs/",
    "tools/", "scripts/", "Makefile", "pyproject.toml", "requirements.txt",
)
_EXCLUDE_PREFIXES = (
    ".claude/",  # Claude tooling captured by draft_rex.py instead
    ".archive/", ".git/", "node_modules/", "__pycache__/",
    "graphify-out/", ".pytest_cache/", ".ruff_cache/",
)


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


def _is_relevant(rel: str) -> bool:
    if any(rel.startswith(p) for p in _EXCLUDE_PREFIXES):
        return False
    return any(rel.startswith(p) for p in _INCLUDE_PREFIXES)


def _observations_file(repo_root: Path) -> Path:
    project_name = repo_root.name or "default"
    return repo_root / ".claude" / "homunculus" / project_name / "observations.jsonl"


def _load_session_files(repo_root: Path) -> tuple[list[str], float, float]:
    obs = _observations_file(repo_root)
    if not obs.exists():
        return [], 0.0, 0.0
    start_ts = _session_start_ts(repo_root)
    files: dict[str, tuple[float, float]] = {}
    try:
        for line in obs.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            file_path = entry.get("file", "")
            ts_iso = entry.get("ts", "")
            if not file_path or not ts_iso:
                continue
            try:
                rel = str(Path(file_path).resolve().relative_to(repo_root)).replace("\\", "/")
            except ValueError:
                continue
            if not _is_relevant(rel):
                continue
            try:
                ts = datetime.strptime(ts_iso, "%Y-%m-%dT%H:%M:%S").timestamp()
            except ValueError:
                continue
            if ts < start_ts:
                continue
            prev = files.get(rel)
            if prev is None:
                files[rel] = (ts, ts)
            else:
                files[rel] = (min(prev[0], ts), max(prev[1], ts))
    except OSError:
        return [], 0.0, 0.0
    if not files:
        return [], 0.0, 0.0
    sorted_files = sorted(files.keys())
    first_ts = min(t[0] for t in files.values())
    last_ts = max(t[1] for t in files.values())
    return sorted_files, first_ts, last_ts


def _devlog_has_today_entry(repo_root: Path) -> bool:
    devlog = repo_root / _DEVLOG_PATH
    if not devlog.exists():
        return False
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        # Match "## YYYY-MM-DD" anywhere in the first 200 lines (DEVLOG entries newest-first)
        head = "\n".join(devlog.read_text(encoding="utf-8").splitlines()[:200])
    except OSError:
        return False
    return bool(re.search(rf"^##\s+{re.escape(today)}\b", head, re.MULTILINE))


def _git(repo_root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), *args],
            stderr=subprocess.DEVNULL, text=True, timeout=5,
        ).strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _commits_since(repo_root: Path, since_ts: float) -> list[str]:
    if since_ts <= 0:
        return []
    iso = datetime.fromtimestamp(since_ts, tz=timezone.utc).isoformat()
    raw = _git(repo_root, "log", f"--since={iso}", "--pretty=format:%h %s", "-n", "20")
    return [ln for ln in raw.splitlines() if ln.strip()]


def _render_template(files: list[str], commits: list[str], branch: str,
                     first_ts: float, last_ts: float) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    file_lines = "\n".join(f"- `{f}` — ?" for f in files)
    commit_lines = "\n".join(f"  - {c}" for c in commits) if commits else "  - (none)"
    first_iso = datetime.fromtimestamp(first_ts, tz=timezone.utc).isoformat(timespec="seconds")
    last_iso = datetime.fromtimestamp(last_ts, tz=timezone.utc).isoformat(timespec="seconds")
    return f"""---
validated: false
date: {today}
---

## {today} — <one-line title?>

### Why
?

### What changed
{file_lines}

### Tests
? (run `python3 -m pytest tests/ -q` to fill, or write "n/a" if docs-only)

### Reste à faire
?

---
<!-- Auto-captured context (do not edit, used by /devlog-promote) -->
<!--
files_modified: {len(files)}
commits_since_session_start:
{commit_lines}
branch: {branch or '(detached)'}
session_window: {first_iso} → {last_iso}
-->
"""


def main() -> None:
    try:
        sys.stdin.read()
    except OSError:
        pass

    repo_root = find_repo_root()
    files, first_ts, last_ts = _load_session_files(repo_root)
    if len(files) < _MIN_FILES:
        sys.exit(0)
    if _devlog_has_today_entry(repo_root):
        sys.exit(0)

    # Don't overwrite if the user is mid-edit on an existing pending draft
    pending = repo_root / _PENDING_FILE
    if pending.exists():
        sys.exit(0)

    branch = _git(repo_root, "branch", "--show-current")
    commits = _commits_since(repo_root, first_ts)
    content = _render_template(files, commits, branch, first_ts, last_ts)

    try:
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text(content, encoding="utf-8")
        print(
            f"\n📝 DEVLOG draft pending ({len(files)} files) — fill template + run /devlog-promote",
            file=sys.stderr,
        )
    except OSError:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
