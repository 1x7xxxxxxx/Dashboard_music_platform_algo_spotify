"""Which code-critic reviews really ran, and for which roadmap task — read from transcripts.

Type: Utility
Uses: the project's Claude Code transcripts (~/.claude/projects/<slug>/**/*.jsonl)
Triggers: tools/dev/require_roadmap_id.py (advisory, R198), tools/dev/roadmap_discipline.py (R197)
Persists in: nothing

A call counts when it is a real `tool_use` — an `Agent`/`Task` whose `subagent_type` is
`code-critic`, or an `engineering-loop` `Workflow` run (its Critic phase runs code-critic) —
AND its input names the task id. The transcripts are PARSED, never grepped: a sentence that
merely cites code-critic proves nothing. Same parsing rule as
`.claude/hooks/require_sweep_before_catalogue.py::proof`.

⚠️ What it cannot see, it says: `None` when no transcript folder exists (CI, another machine)
— never an empty list, which would read as « no critic ran ». And the engineering-loop builds
its critic prompt from the FINDINGS, so a loop run counts only if its args name the Rnnn
(code-critic, 2026-09-26).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

WINDOW_S = 7 * 86400
_ROOT = Path(__file__).resolve().parents[2]


def transcripts_dir(repo: Path = _ROOT) -> Path:
    override = os.environ.get("HOOK_TRANSCRIPTS_DIR")
    if override:
        return Path(override)
    slug = "-" + str(repo).strip("/").replace("/", "-").replace("_", "-")
    return Path.home() / ".claude" / "projects" / slug


def _is_critic(c: dict) -> bool:
    inp = c.get("input") or {}
    if c.get("name") in ("Agent", "Task") and inp.get("subagent_type") == "code-critic":
        return True
    return c.get("name") == "Workflow" and (
        inp.get("name") == "engineering-loop"
        or "engineering-loop" in str(inp.get("scriptPath", "")))


def critic_calls(root: Path | None = None, since: float | None = None) -> list[dict] | None:
    """Every critic call in the window: [{'ts': epoch, 'text': its input as text}]."""
    root = transcripts_dir() if root is None else root
    if not root.is_dir():
        return None
    since = time.time() - WINDOW_S if since is None else since
    out: list[dict] = []
    for f in root.rglob("*.jsonl"):
        try:
            if f.stat().st_mtime < since:
                continue
            fh = f.open(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"tool_use"' not in line or ("code-critic" not in line
                                                and "engineering-loop" not in line):
                    continue
                try:
                    rec = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                content = (rec.get("message") or {}).get("content")
                for c in content if isinstance(content, list) else []:
                    if isinstance(c, dict) and c.get("type") == "tool_use" and _is_critic(c):
                        out.append({"ts": _epoch(rec.get("timestamp")),
                                    "text": json.dumps(c.get("input") or {}, ensure_ascii=False)})
    return out


def _epoch(stamp) -> float:
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def names(call: dict, task: str) -> bool:
    """The call's input names `task` as a whole token (R19 is not R196)."""
    import re
    return re.search(rf"\b{re.escape(task)}\b", call["text"]) is not None


def critic_calls_naming(task: str, before: float | None = None,
                        root: Path | None = None) -> list[dict] | None:
    calls = critic_calls(root)
    if calls is None:
        return None
    return [c for c in calls if names(c, task) and (before is None or c["ts"] <= before)]
