#!/usr/bin/env python3
"""
PostToolUse hook — Continuous learning observation logger.

Captures file edits into .claude/homunculus/<project>/observations.jsonl,
where <project> is auto-derived from the repo root directory name.
This feeds the continuous-learning skill: patterns are extracted manually
via the 'continuous-learning' skill at session end.

Triggers on: Write, Edit tool calls only.
Always exits 0 — never blocks.

---
rex: []
---
"""

import json
import os
import sys
import time
from pathlib import Path


# Observe code-y / config-y files; skip generated / vendored trees.
_OBSERVE_SUFFIXES = (".py", ".md", ".yml", ".yaml", ".json", ".sh", ".ts", ".js", ".tsx", ".jsx")
_SKIP_PATHS = (".venv", "__pycache__", ".git", "node_modules", "dist", "build", ".next", "target")

_MAX_OBS_FILE_KB = 500   # Rotate observations log if > 500 KB
_MAX_OBS_ENTRIES = 2000  # Hard cap to prevent unbounded growth


def find_repo_root() -> Path:
    path = Path(os.getcwd())
    while path != path.parent:
        if (path / ".claude").exists():
            return path
        path = path.parent
    return Path(os.getcwd())


def should_observe(file_path: str) -> bool:
    if not any(file_path.endswith(s) for s in _OBSERVE_SUFFIXES):
        return False
    if any(skip in file_path for skip in _SKIP_PATHS):
        return False
    return True


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path or not should_observe(file_path):
        sys.exit(0)

    repo_root = find_repo_root()
    project_name = repo_root.name or "default"
    obs_dir = repo_root / ".claude" / "homunculus" / project_name
    obs_dir.mkdir(parents=True, exist_ok=True)
    obs_file = obs_dir / "observations.jsonl"

    # Rotate if too large
    if obs_file.exists() and obs_file.stat().st_size > _MAX_OBS_FILE_KB * 1024:
        archive = obs_dir / f"observations.{int(time.time())}.jsonl.bak"
        obs_file.rename(archive)

    # Build observation entry
    entry: dict = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tool": tool_name,
        "file": file_path,
    }

    # For Edit: capture old/new snippet (first 80 chars each)
    if tool_name == "Edit":
        old = tool_input.get("old_string", "")[:80].replace("\n", "↵")
        new = tool_input.get("new_string", "")[:80].replace("\n", "↵")
        entry["edit"] = {"old": old, "new": new}

    # Append to JSONL
    try:
        with open(obs_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Enforce entry cap
        lines = obs_file.read_text(encoding="utf-8").splitlines()
        if len(lines) > _MAX_OBS_ENTRIES:
            obs_file.write_text(
                "\n".join(lines[-_MAX_OBS_ENTRIES:]) + "\n",
                encoding="utf-8"
            )
    except OSError:
        pass  # Never block on observation failure

    sys.exit(0)


if __name__ == "__main__":
    main()
