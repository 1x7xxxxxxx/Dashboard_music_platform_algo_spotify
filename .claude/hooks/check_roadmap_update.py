#!/usr/bin/env python3
"""
Hook PostToolUse — Reminder to update the active roadmap after Python code changes.

Triggered after every Write or Edit on a .py file.
Checks if the ACTIVE roadmap file was modified in the last 5 minutes.
If not, prints a soft reminder. Always exits 0 (non-blocking).

---
rex:
  - date: 2026-06-14
    issue: "Silent no-op: repo_root = dirname(hook_dir) gave .claude not repo root, tracker mtime never read"
    fix: "repo_root = dirname(dirname(hook_dir)) — was .claude, now repo root, so trackers resolve"
    severity: warn
  - date: 2026-08-03
    issue: "Tracked `.claude/dev-docs/ROADMAP.md`, an unrendered bootstrap template nothing ever wrote, while real status lived in roadmap/checklist.md. The mtime was always stale, so the reminder fired on every .py edit — always-true, hence uninformative. The message also named BRICKS.md and DEPLOYMENT.md, neither of which exists in this repo."
    fix: "Tracks roadmap/checklist.md (actif); message names the two real files; a missing tracker now says so instead of exiting silently."
    ref: "roadmap-two-files-2026-08-03"
    severity: warn
---
"""
import json
import os
import sys
import time


# The ACTIVE roadmap file is the status signal (two-file split, 2026-08-03).
# `archive.md` is deliberately absent: it only ever receives what already shipped,
# so its mtime says nothing about whether current work was recorded.
#
# Until 2026-08-03 this tuple held `.claude/dev-docs/ROADMAP.md`, an unrendered
# bootstrap template nothing ever wrote. The freshness check was therefore true on
# every single run, and a reminder that always fires carries no information —
# it trains the reader to skip it, which is worse than not reminding at all.
_TRACKER_PATHS = (
    ".claude/dev-docs/roadmap/checklist.md",
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

    # Resolve tracker paths relative to repo root.
    # hook_dir is .claude/hooks → repo root is TWO levels up, not one.
    hook_dir = os.path.dirname(os.path.abspath(__file__))   # .claude/hooks/
    repo_root = os.path.dirname(os.path.dirname(hook_dir))  # .claude/hooks → .claude → repo root

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
        # Every tracker is missing. Exiting silently here is how this hook spent
        # weeks measuring nothing — say it instead, so the miss is visible.
        print(f"📋 roadmap tracker not found: {', '.join(_TRACKER_PATHS)} — this hook is blind")
        sys.exit(0)

    if youngest_age > _FRESHNESS_WINDOW_S:
        fname = os.path.basename(file_path)
        print(
            f"📋 {fname} modified — update `.claude/dev-docs/roadmap/checklist.md` "
            f"(actif). Delivered? `Spawn roadmap-keeper` rotates it into archive.md."
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
