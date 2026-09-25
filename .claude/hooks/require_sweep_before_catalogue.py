#!/usr/bin/env python3
"""PreToolUse (Bash): no commit writes to the error-class catalogue without a REAL sweep.

Type: Hook
Uses: git, the project's Claude Code transcripts (~/.claude/projects/<slug>/**/*.jsonl)
Triggers: every Bash call; acts only on a `git commit` whose diff adds a class or a
          `(récidive)` line to .claude/dev-docs/error-classes.md
Persists in: .claude/sessions/sweep-override.log (only when SWEEP_OVERRIDE is used)

Why this exists
---------------
Rule 14 says « Spawn sibling-sweeper BEFORE writing the fix », and the CLAUDE.md rule on
the engineering loop says « ≥ 2 findings -> RUN engineering-loop ». Both were prose. On
2026-09-25 the workflow map measured it: sibling-sweeper 77 calls in 30 days, but
`engineering-loop` ZERO — including a day with several multi-finding batches — and the
only check on a sweep was the `swept:` TEXT of the entry, validated in CI for its form.

A hook cannot spawn an agent. It CAN refuse the one gesture that closes the loop without
it: committing the catalogue entry. So:

  * the diff (working tree vs HEAD — `git add -A && git commit` runs in one command, so
    the index is still empty when this hook fires) adds >= 1 class or `(récidive)` line
    -> a `sibling-sweeper` Agent call, or an `engineering-loop` Workflow call, must exist
    in the project's transcripts of the last 48 h;
  * it adds >= 2 -> an `engineering-loop` Workflow call must exist.

The last 48 h of the PROJECT, not only this session: a sweep in session N and a commit in
session N+1 (`/resume`, a compacted night) must pass — objection by code-critic, else the
escape hatch becomes the reflex. The transcripts are PARSED (a tool_use whose input names
the agent), never grepped: a sentence that merely CITES sibling-sweeper proves nothing.

Escape: `SWEEP_OVERRIDE=<reason>` in the command. Logged, never silent.

---
rex: []
---
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

CATALOGUE = ".claude/dev-docs/error-classes.md"
WINDOW_S = 48 * 3600
_CLASS_HEAD = re.compile(r"^\+## [a-z0-9][a-z0-9-]+\s*$")
_RECURRENCE = re.compile(r"^\+\s+- \d{4}-\d{2}-\d{2} \(récidive\):")
_SPLIT = re.compile(r"&&|\|\||;|\|")


def is_git_commit(command: str) -> bool:
    """A segment whose COMMAND is `git … commit` — not a word inside an argument."""
    for seg in _SPLIT.split(command):
        try:
            words = shlex.split(seg)
        except ValueError:
            words = seg.split()
        while words and re.match(r"^[A-Z_][A-Z0-9_]*=", words[0]):
            words = words[1:]                      # VAR=value git commit
        if words and Path(words[0]).name == "git":
            args = words[1:]
            while args and args[0] in ("-C", "-c"):   # `git -C dir commit`
                args = args[2:]
            if args and args[0] == "commit":
                return True
    return False


def added_entries(diff: str) -> int:
    return sum(1 for line in diff.splitlines()
               if _CLASS_HEAD.match(line) or _RECURRENCE.match(line))


def transcripts_dir(repo: Path) -> Path:
    override = os.environ.get("HOOK_TRANSCRIPTS_DIR")
    if override:
        return Path(override)
    slug = "-" + str(repo).strip("/").replace("/", "-").replace("_", "-")
    return Path.home() / ".claude" / "projects" / slug


def proof(root: Path, now: float | None = None) -> set[str]:
    """{'sibling-sweeper', 'engineering-loop'} ∩ what was really invoked in the window."""
    now = time.time() if now is None else now
    found: set[str] = set()
    if not root.is_dir():
        return found
    for f in root.rglob("*.jsonl"):
        try:
            if now - f.stat().st_mtime > WINDOW_S:
                continue
            fh = f.open(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"tool_use"' not in line or ("sibling-sweeper" not in line
                                                and "engineering-loop" not in line):
                    continue                        # cheap prefilter; the parse decides
                try:
                    msg = json.loads(line).get("message") or {}
                except (json.JSONDecodeError, ValueError, AttributeError):
                    continue
                content = msg.get("content")
                for c in content if isinstance(content, list) else []:
                    if not isinstance(c, dict) or c.get("type") != "tool_use":
                        continue
                    inp = c.get("input") or {}
                    if c.get("name") in ("Agent", "Task") and \
                            inp.get("subagent_type") == "sibling-sweeper":
                        found.add("sibling-sweeper")
                    if c.get("name") == "Workflow" and (
                            inp.get("name") == "engineering-loop"
                            or "engineering-loop" in str(inp.get("scriptPath", ""))):
                        found.add("engineering-loop")
        if found == {"sibling-sweeper", "engineering-loop"}:
            break
    return found


def verdict(n_entries: int, invoked: set[str]) -> str | None:
    """None when the commit may go; otherwise the message that blocks it."""
    if n_entries == 0:
        return None
    if n_entries >= 2 and "engineering-loop" not in invoked:
        return (f"{n_entries} entrées ajoutées au catalogue (classes ou récidives) et aucun "
                "`engineering-loop` lancé sur ce projet depuis 48 h. Règle de CLAUDE.md : "
                "≥ 2 trouvailles → Workflow({name: \"engineering-loop\", args: [...]}).")
    if not invoked:
        return ("une classe ou une récidive est ajoutée au catalogue et aucun "
                "`sibling-sweeper` (ni `engineering-loop`) n'a tourné sur ce projet depuis "
                "48 h. Règle 14 : Spawn sibling-sweeper sur cette classe AVANT d'écrire au "
                "catalogue — le défaut existe peut-être déjà ailleurs.")
    return None


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    command = (data.get("tool_input") or {}).get("command", "")
    if not command or not is_git_commit(command):
        return 0
    repo = Path(data.get("cwd") or os.getcwd())
    try:
        top = subprocess.run(["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        if not top:
            return 0
        diff = subprocess.run(["git", "-C", top, "diff", "HEAD", "-U0", "--", CATALOGUE],
                              capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    n = added_entries(diff)
    if n == 0:
        return 0
    m = re.search(r"\bSWEEP_OVERRIDE=(\S+)", command)
    if m:
        log = Path(top) / ".claude" / "sessions" / "sweep-override.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} entries={n} reason={m.group(1)}\n")
        return 0
    msg = verdict(n, proof(transcripts_dir(Path(top))))
    if msg is None:
        return 0
    print(f"🚫 BLOCKED — {msg}\n   Échappatoire consignée : SWEEP_OVERRIDE=<raison> git commit …",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
