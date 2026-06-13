#!/usr/bin/env python3
"""
Hook PostToolUse — Reminder to update the live tracker after Python code changes.

Triggered after every Write or Edit on a .py file under src/.
Checks if the live tracker (roadmap/checklist.md) or DEVLOG.md was modified
in the last 5 minutes. If not, prints a soft reminder. Always exits 0 (non-blocking).

---
rex:
  - date: 2026-05-14
    issue: "Hook was a no-op: _INCLUDE='src/Application' mismatched repo, tracker paths pointed to archived/non-existent files"
    fix: "Repointed to roadmap/checklist.md + DEVLOG.md, _INCLUDE='src' with hook/script/test excludes"
    severity: warn
    ref: DEVLOG#2026-05-14
  - date: 2026-06-13
    issue: "Still a silent no-op: repo_root = dirname(hook_dir) gave .claude (not repo root), tracker mtime never read"
    fix: "repo_root = dirname(dirname(hook_dir)) — .claude/hooks → .claude → repo root, so checklist.md/DEVLOG.md resolve"
    severity: warn
    ref: DEVLOG#2026-06-13
---
"""
import json
import os
import sys
import time


_TRACKER_PATHS = (
    ".claude/dev-docs/roadmap/checklist.md",
    "DEVLOG.md",
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
    _INCLUDE = "src" + os.sep
    _EXCLUDE = (
        os.sep + "tests" + os.sep,
        os.path.join(".claude", "hooks"),
        os.path.join(".claude", "scripts"),
        os.path.join("airflow", "debug_dag"),
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
        sys.exit(0)

    if youngest_age > _FRESHNESS_WINDOW_S:
        fname = os.path.basename(file_path)
        print(
            f"{fname} modified — remember to update roadmap/checklist.md or DEVLOG.md",
            file=sys.stderr,
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
