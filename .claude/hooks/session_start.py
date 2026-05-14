#!/usr/bin/env python3
"""
SessionStart hook — auto-injects last session state at conversation start.
Reads .claude/sessions/latest.md and prints it as context so /resume
becomes optional after a /clear or new session.
Registered under SessionStart in settings.json.

---
rex: []
---
"""

import json
import sys
import os
import time
from pathlib import Path


def find_repo_root() -> Path:
    path = Path(os.getcwd())
    while path != path.parent:
        if (path / ".claude").exists():
            return path
        path = path.parent
    return Path(os.getcwd())


def _brick_banner(repo_root: Path) -> str | None:
    """Return a resume banner if a brick session is active, else None."""
    state_file = repo_root / ".claude" / "sessions" / "brick_session.json"
    if not state_file.exists():
        return None
    try:
        st = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    status = st.get("status", "")
    bid = st.get("brick_id", "?")
    it = st.get("iterations", 0)
    last_step = st.get("last_step") or "(not started)"

    if status == "running":
        wts = st.get("working_tree_snapshot") or {}
        fc = wts.get("file_count", 0)
        return (
            f"\n=== Active brick session ===\n"
            f"Brick {bid} — iteration {it}, last step: {last_step}\n"
            f"Status: running. Working tree: {fc} file(s) touched.\n"
            f"To resume: type `/work-brick {bid}`\n"
            f"To abandon: edit .claude/sessions/brick_session.json → status=paused\n"
            f"=== End brick session ===\n"
        )
    if status in ("blocked", "paused"):
        reason = st.get("blocker_reason") or "(no reason recorded)"
        return (
            f"\n=== Brick session halted ===\n"
            f"Brick {bid} — status: {status}\n"
            f"Reason: {reason}\n"
            f"Inspect .claude/sessions/brick_session.json, then either:\n"
            f"  - fix the blocker and re-launch `/work-brick {bid}`\n"
            f"  - delete the state file to start fresh\n"
            f"=== End brick session ===\n"
        )
    return None


def _write_session_marker(repo_root: Path) -> None:
    """Record session start time for draft_rex.py to scope this session's edits."""
    marker = repo_root / ".claude" / "sessions" / ".session-start-ts"
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"{time.time()}\n", encoding="utf-8")
    except OSError:
        pass


def main():
    repo_root = find_repo_root()
    _write_session_marker(repo_root)
    latest = repo_root / ".claude" / "sessions" / "latest.md"

    brick_banner = _brick_banner(repo_root)
    if brick_banner:
        print(brick_banner)

    if not latest.exists():
        sys.exit(0)

    content = latest.read_text(encoding="utf-8", errors="ignore")

    if len(content.strip()) < 100:
        sys.exit(0)

    print("--- Auto-loaded prior session context ---")
    print(content)
    print("--- End of prior session context ---")
    print("Tip: run /resume for full sprint + ROADMAP state.")
    sys.exit(0)


if __name__ == "__main__":
    main()
