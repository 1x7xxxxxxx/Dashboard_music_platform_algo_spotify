#!/usr/bin/env python3
"""
Stop hook — drafts REX proposals from this session's tool modifications.

Reads observations.jsonl entries since session start (marker file written by session_start.py),
filters to files under .claude/{agents,skills,commands,rules,hooks,scripts}, groups by file,
and writes .claude/sessions/pending-rex.md with one proposal per modified tool. Silent if no
tool was modified. Never blocks — exit 0 on any error.

---
rex: []
---
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_SESSION_MARKER_FILE = ".claude/sessions/.session-start-ts"
_PENDING_FILE = ".claude/sessions/pending-rex.md"
_TOOL_DIRS = (
    ".claude/agents/", ".claude/skills/", ".claude/commands/",
    ".claude/rules/", ".claude/hooks/", ".claude/scripts/",
)
_FALLBACK_WINDOW_SEC = 2 * 60 * 60  # 2h


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


def _is_tool_path(rel: str) -> bool:
    return any(rel.startswith(d) for d in _TOOL_DIRS) and (rel.endswith(".md") or rel.endswith(".py"))


def _observations_file(repo_root: Path) -> Path:
    """Mirror of observe.py — homunculus path is keyed by repo root dir name."""
    project_name = repo_root.name or "default"
    return repo_root / ".claude" / "homunculus" / project_name / "observations.jsonl"


def _load_session_edits(repo_root: Path) -> dict[str, list[str]]:
    obs = _observations_file(repo_root)
    if not obs.exists():
        return {}
    start_ts = _session_start_ts(repo_root)
    by_file: dict[str, list[str]] = {}
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
            abs_path = Path(file_path)
            try:
                rel = abs_path.resolve().relative_to(repo_root)
            except ValueError:
                continue
            rel_str = str(rel).replace("\\", "/")
            if not _is_tool_path(rel_str):
                continue
            try:
                entry_ts = datetime.strptime(ts_iso, "%Y-%m-%dT%H:%M:%S").timestamp()
            except ValueError:
                continue
            if entry_ts < start_ts:
                continue
            by_file.setdefault(rel_str, []).append(ts_iso)
    except OSError:
        return {}
    return by_file


def _render_pending(by_file: dict[str, list[str]]) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    header = (
        "# Pending REX drafts — review and promote via `/rex-promote` or `/retro`\n\n"
        "> One proposal per tool modified this session.\n"
        "> Edit `issue:` + `fix:` + `severity:` as needed, then set `validated: true` to promote.\n"
        "> Delete the block entirely to skip a proposal (no REX entry for that tool).\n"
        f"> Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n\n"
    )
    sections = []
    for rel, ts_list in sorted(by_file.items()):
        edits = len(ts_list)
        first, last = min(ts_list), max(ts_list)
        sections.append(
            f"## {rel}\n"
            f"```yaml\n"
            f"target: {rel}\n"
            f"validated: false\n"
            f"entry:\n"
            f"  date: {today}\n"
            f"  issue: \"?\"\n"
            f"  fix: \"?\"\n"
            f"  severity: info\n"
            f"  # ref: DEVLOG#{today} or brick id (optional)\n"
            f"# observed: {edits} edit(s), first {first}, last {last}\n"
            f"```\n"
        )
    return header + "\n".join(sections)


def main() -> None:
    try:
        sys.stdin.read()
    except OSError:
        pass

    repo_root = find_repo_root()
    by_file = _load_session_edits(repo_root)
    if not by_file:
        sys.exit(0)

    content = _render_pending(by_file)
    pending = repo_root / _PENDING_FILE
    try:
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text(content, encoding="utf-8")
        print(f"\n📝 {len(by_file)} REX draft(s) pending — run /retro or /rex-promote", file=sys.stderr)
    except OSError:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
