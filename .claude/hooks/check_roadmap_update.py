#!/usr/bin/env python3
"""
Hook PostToolUse — Reminder to update ROADMAP.md after Python code changes.

Triggered after every Write or Edit on a .py file.
Checks if ROADMAP.md was modified in the last 5 minutes.
If not, prints a soft reminder. Always exits 0 (non-blocking).

---
rex: []
---
"""
import json
import os
import sys
import time


_TRACKER_PATHS = (
    ".claude/dev-docs/ROADMAP.md",
    ".claude/dev-docs/BRICKS.md",
    ".claude/dev-docs/DEPLOYMENT.md",
)
_FRESHNESS_WINDOW_S = 300  # 5 minutes


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # Only trigger on Python file writes/edits
    if tool_name not in ("Write", "Edit") or not file_path.endswith(".py"):
        sys.exit(0)

    # Only fire for application source files — not tests, hooks, scripts, configs
    _INCLUDE = os.path.join("src", "Application")
    _EXCLUDE = (
        os.path.join("src", "Application", "tests"),
        os.path.join(".claude", "hooks"),
        os.path.join(".claude", "scripts"),
        "conftest.py",
        "setup.py",
        "setup.cfg",
    )
    if _INCLUDE not in file_path:
        sys.exit(0)
    if any(excl in file_path for excl in _EXCLUDE):
        sys.exit(0)

    # Resolve tracker paths relative to repo root
    hook_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(hook_dir)  # .claude/ → repo root

    now = time.time()
    youngest_age: float | None = None
    for rel in _TRACKER_PATHS:
        full = os.path.join(repo_root, rel)
        if not os.path.exists(full):
            continue
        age = now - os.path.getmtime(full)
        if youngest_age is None or age < youngest_age:
            youngest_age = age

    if youngest_age is None:
        sys.exit(0)

    if youngest_age > _FRESHNESS_WINDOW_S:
        fname = os.path.basename(file_path)
        print(
            f"📋 {fname} modified — remember to update ROADMAP.md / BRICKS.md / DEPLOYMENT.md"
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
