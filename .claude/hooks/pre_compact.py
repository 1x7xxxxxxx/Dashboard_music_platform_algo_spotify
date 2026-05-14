#!/usr/bin/env python3
"""PreCompact hook — saves session state before Claude compacts context.
---
rex: []
---
"""

import json
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path


def find_repo_root() -> Path:
    path = Path(os.getcwd())
    while path != path.parent:
        if (path / ".claude").exists():
            return path
        path = path.parent
    return Path(os.getcwd())


def _get_git_branch(repo_root: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=repo_root, timeout=5,
        )
        return r.stdout.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def _get_git_files(repo_root: Path) -> list[str]:
    _SKIP = (".pyc", "__pycache__", "mlruns/")
    try:
        r = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True, cwd=repo_root, timeout=5,
        )
        return [l for l in r.stdout.strip().splitlines() if not any(p in l for p in _SKIP)]
    except (OSError, subprocess.TimeoutExpired):
        return []


def _get_last_devlog(repo_root: Path) -> str:
    devlog = repo_root / "DEVLOG.md"
    if not devlog.exists():
        return "N/A"
    for line in reversed(devlog.read_text(encoding="utf-8", errors="ignore").splitlines()):
        if line.startswith("## "):
            return line[3:].strip()
    return "N/A"


def _extract_state_lines(lines: list[str]) -> list[str]:
    """Extract '## Current state' and '## Open questions' sections (max 25 lines total)."""
    result: list[str] = []
    in_state = False
    in_questions = False
    for line in lines:
        if line.startswith("## Current state"):
            in_state, in_questions = True, False
            continue
        if line.startswith("## Open questions"):
            in_state, in_questions = False, True
            result.append("**Open questions:**")
            continue
        if line.startswith("## "):
            in_state = in_questions = False
            continue
        if (in_state or in_questions) and line.strip():
            result.append(line)
        if len(result) >= 25:
            break
    return result or ["(no current state)"]


def _get_wip_summary(wip_dir: Path) -> str:
    if not wip_dir.exists():
        return "None"
    folders = [d for d in wip_dir.iterdir() if d.is_dir() and d.name != "__pycache__"]
    if not folders:
        return "None"
    parts = []
    for folder in folders:
        ctx = folder / "context.md"
        if not ctx.exists():
            parts.append(f"**{folder.name}** — no context.md")
            continue
        lines = ctx.read_text(encoding="utf-8", errors="ignore").splitlines()
        parts.append(f"**{folder.name}**\n" + "\n".join(_extract_state_lines(lines)))
    return "\n\n".join(parts)


def _build_content(timestamp: str, branch: str, git_str: str, devlog: str, wip: str) -> str:
    return (
        f"# Session State — {timestamp}\n"
        f"*Saved by PreCompact hook before context compaction*\n\n"
        f"## Git branch\n{branch}\n\n"
        f"## Git status\n{git_str}\n\n"
        f"## Last DEVLOG entry\n{devlog}\n\n"
        f"## Active WIP\n{wip}\n\n"
        f"## Resume instructions\n"
        f"After /clear or session restart:\n"
        f"1. Run `/resume` to reload sprint + WIP state\n"
        f"2. Check `.claude/sessions/session-{timestamp}.md` for pre-compaction context\n"
        f"3. Re-run `python3 -m pytest tests/ -q` to confirm test state\n\n"
        f"## Notes\n"
        f"*(Add any in-progress context here manually if needed)*\n"
    )


def main() -> None:
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        pass

    repo_root = find_repo_root()
    sessions_dir = repo_root / ".claude" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch = _get_git_branch(repo_root)
    git_files = _get_git_files(repo_root)
    git_str = "\n".join(f"  {l}" for l in git_files[:10]) or "  (clean)"
    devlog = _get_last_devlog(repo_root)
    wip_dir = repo_root / ".claude" / "dev-docs" / "work-in-progress"
    wip = _get_wip_summary(wip_dir)

    content = _build_content(timestamp, branch, git_str, devlog, wip)
    session_file = sessions_dir / f"session-{timestamp}.md"
    session_file.write_text(content, encoding="utf-8")

    all_sessions = sorted(sessions_dir.glob("session-*.md"), key=lambda p: p.stat().st_mtime)
    for old in all_sessions[:-10]:
        old.unlink()

    (sessions_dir / "latest.md").write_text(content, encoding="utf-8")
    print(f"[PreCompact] Session state saved to .claude/sessions/session-{timestamp}.md")
    sys.exit(0)


if __name__ == "__main__":
    main()
