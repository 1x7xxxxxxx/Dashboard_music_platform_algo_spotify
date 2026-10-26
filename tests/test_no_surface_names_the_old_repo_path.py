"""No config surface names an absolute path to the repo (R663).

Type: Sub
Uses: .claude/settings.json, docker-compose*.yml
Depends on: nothing at runtime — reads the files
Persists in: nothing

The repo moved from /home/timothe/streamlytics to /home/timothe/projects/streamlytics
around 2026-10-20. Twenty hook commands in settings.json still fell back to the old path
when `git rev-parse` failed, and stopped containers kept bind mounts on it (Docker
recreated empty directories there). A hard-coded checkout path goes stale on the next move;
the fallback is now `$CLAUDE_PROJECT_DIR`, set by Claude Code for every hook.

guard_scope: settings.json hook commands and the compose files (no `/home/<user>/` path).
NOT covered: mounts of containers already created (`docker inspect` — machine state, not
the tree), and absolute paths in scripts under tools/ or .claude/hooks/.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_HOME_PATH = re.compile(r"/home/[^/\s\"']+/")


def _commands(node: object) -> list[str]:
    if isinstance(node, dict):
        out = [node["command"]] if isinstance(node.get("command"), str) else []
        return out + [c for v in node.values() for c in _commands(v)]
    if isinstance(node, list):
        return [c for v in node for c in _commands(v)]
    return []


def test_no_hook_command_names_a_home_path():
    settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    commands = _commands(settings)
    assert commands, "no hook command read — the walker no longer matches settings.json"
    bad = [c for c in commands if _HOME_PATH.search(c)]
    assert not bad, f"{len(bad)} hook command(s) name an absolute home path: {bad[:2]}"


def test_no_compose_file_mounts_a_home_path():
    files = sorted(ROOT.glob("docker-compose*.yml"))
    assert files, "no docker-compose*.yml found"
    bad = [f"{f.name}:{i}" for f in files
           for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
           if not ln.lstrip().startswith("#") and _HOME_PATH.search(ln)]
    assert not bad, f"compose lines mounting an absolute home path: {bad}"
