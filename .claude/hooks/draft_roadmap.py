#!/usr/bin/env python3
"""Stop hook — list the actions this session identified that the roadmap does not carry.

Type: Hook
Uses: git log (commits since the session start), engineering-loop workflow journals,
      .claude/dev-docs/roadmap/checklist.md
Triggers: Stop (advisory — never blocks)
Persists in: .claude/sessions/pending-roadmap.md

Why this exists
---------------
Measured 2026-09-25: nothing made an identified action ENTER the roadmap. Every mechanism
handled the exit (rotation to archive.md) or the consistency of what was already written;
~9 actions were identified that day and 0 written. A blocking hook was rejected by
code-critic: triggered by a line the model must first write, it never sees the action the
model FORGOT. This hook only suggests, from two sources:

  * `Ouvert :` / `Reste :` lines of this session's commit messages — a convention.

⚠️ A second source was designed and DROPPED on 2026-09-25: the `roadmap_action` of
engineering-loop manifests. It is computed in the script's post-processing
(engineering-loop.js:357) and returned to the main context only — a workflow script cannot
write a file, and the per-agent journal never carries it. Reading journals for it found
nothing on a session that had run the loop three times: a link that cannot bind.

What it cannot see, it does not claim: an action written nowhere stays invisible. The
blocking half lives where a quantity is measured —
tests/test_a_measured_debt_has_its_roadmap_line.py.

---
rex: []
---
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

_SESSION_MARKER_FILE = ".claude/sessions/.session-start-ts"
_PENDING_FILE = ".claude/sessions/pending-roadmap.md"
_CHECKLIST = ".claude/dev-docs/roadmap/checklist.md"
_FALLBACK_WINDOW_SEC = 6 * 3600
_OPEN_LINE = re.compile(r"^\s*(?:Ouvert|Reste)\s*:\s*(.+?)\s*$", re.M)


def find_repo_root() -> Path:
    p = Path(os.getcwd())
    while p != p.parent:
        if (p / ".claude").exists():
            return p
        p = p.parent
    return Path(os.getcwd())


def session_start_ts(repo_root: Path) -> float:
    marker = repo_root / _SESSION_MARKER_FILE
    try:
        return float(marker.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return time.time() - _FALLBACK_WINDOW_SEC


def commit_actions(repo_root: Path, since: float) -> list[str]:
    """`Ouvert :` / `Reste :` lines of the commit messages written since `since`."""
    try:
        out = subprocess.run(["git", "-C", str(repo_root), "log", f"--since=@{int(since)}",
                              "--format=%B%x1e"], capture_output=True, text=True,
                             timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [m.group(1) for m in _OPEN_LINE.finditer(out)]


def missing(candidates: list[str], checklist_text: str) -> list[str]:
    """Candidates whose first 40 characters appear nowhere in the checklist."""
    seen, out = set(), []
    for c in candidates:
        key = c.strip()[:40]
        if key and key not in seen and key not in checklist_text:
            seen.add(key)
            out.append(c.strip())
    return out


def main() -> int:
    try:
        sys.stdin.read()
    except OSError:
        pass
    root = find_repo_root()
    since = session_start_ts(root)
    try:
        checklist = (root / _CHECKLIST).read_text(encoding="utf-8")
    except OSError:
        return 0
    todo = missing(commit_actions(root, since), checklist)
    if not todo:
        return 0
    body = ("# Actions de la séance absentes de la roadmap\n\n"
            "Proposées par `.claude/hooks/draft_roadmap.py` — à inscrire dans "
            "`.claude/dev-docs/roadmap/checklist.md` (index + bloc, avec la commande qui "
            "mesure), ou à écarter en le disant.\n\n"
            + "".join(f"- [ ] {t}\n" for t in todo))
    try:
        pending = root / _PENDING_FILE
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text(body, encoding="utf-8")
        print(f"\n🗺️  {len(todo)} action(s) de la séance absente(s) de la roadmap — "
              f"voir {_PENDING_FILE}", file=sys.stderr)
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
