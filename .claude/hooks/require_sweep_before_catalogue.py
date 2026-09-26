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

  * the working-tree catalogue, compared with HEAD's (`git add -A && git commit` runs in
    one command, so the index is still empty when this hook fires), adds >= 1 class id or
    (class, date) `(récidive)` pair — counted by SET difference, so a block that only
    MOVES (the dormant ranking done by `make error-health`) adds nothing
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
from collections import Counter
from pathlib import Path

CATALOGUE = ".claude/dev-docs/error-classes.md"
WINDOW_S = 48 * 3600
_CLASS_HEAD = re.compile(r"^## ([a-z0-9][a-z0-9-]+)\s*$")
_RECURRENCE = re.compile(r"^\s+- (\d{4}-\d{2}-\d{2}) \(récidive\):")
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


def _entries(text: str) -> tuple[set[str], Counter]:
    """(class ids, multiset of (class, date) récidive pairs) of one catalogue text."""
    ids: set[str] = set()
    pairs: Counter = Counter()
    current = None
    for line in text.splitlines():
        head = _CLASS_HEAD.match(line)
        if head:
            current = head.group(1)
            ids.add(current)
        elif line.startswith("## "):
            current = None                           # a section that is not a class
        elif current:
            rec = _RECURRENCE.match(line)
            if rec:
                pairs[(current, rec.group(1))] += 1
    return ids, pairs


def added_entries(before: str, after: str) -> int:
    """Classes and récidives ADDED, by SET difference — never by counting `+` lines.

    ⚠️ Counting the `+` lines of a diff counted a MOVED block as an added one: measured
    on `1be1c8b` (one récidive, the block moved above the dormant separator) the old
    counter returned **2**; on `f30d724`, **4**. Since `make error-health` ranks the
    catalogue itself (`rank_catalogue`), every regeneration moves blocks, and a line
    counter would block or over-count each time. An id that already existed, a
    récidive already dated, is not added.
    """
    ids_before, pairs_before = _entries(before)
    ids_after, pairs_after = _entries(after)
    return len(ids_after - ids_before) + sum((pairs_after - pairs_before).values())


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


# ── R186 (2026-09-26): the sweep bound to ITS class, by content ─────────────────────────
# Until then ANY sweeper call in the window let ANY class through — a sweep made for
# another defect counted. An agent id copied into the entry was rejected (nothing proves it
# is transcribed faithfully); the binding is by CONTENT instead: the sweep's prompt or its
# result must mention the new class's id or one of the files the class cites.
_CITED = re.compile(r"(?:^|[\s`(])((?:src|tools|tests|airflow|\.claude|\.github|migrations|"
                    r"deploy|docs)/[\w./-]+\.\w+)")
_GENERIC = {"__init__.py", "conftest.py", "Makefile", "README.md", "error-classes.md"}


def added_bodies(before: str, after: str) -> dict[str, str]:
    """{class id: its body in `after`} for every class ADDED or given a NEW récidive. Pure."""
    ids_before, pairs_before = _entries(before)
    ids_after, pairs_after = _entries(after)
    touched = (ids_after - ids_before) | {c for c, _ in (pairs_after - pairs_before)}
    bodies: dict[str, str] = {}
    current, buf = None, []
    for line in after.splitlines() + ["## "]:
        head = _CLASS_HEAD.match(line)
        if head or line.startswith("## "):
            if current in touched:
                bodies[current] = "\n".join(buf)
            current, buf = (head.group(1) if head else None), []
        elif current:
            buf.append(line)
    return bodies


def anchors(cid: str, body: str) -> set[str]:
    """What a sweep of this class must mention: its id, the files it cites. Pure."""
    out = {cid}
    for path in _CITED.findall(body):
        name = path.rsplit("/", 1)[-1]
        out.add(path)
        if name not in _GENERIC and len(name) > 6:
            out.add(name)
    return out


def sweep_texts(root: Path, now: float | None = None) -> list[str]:
    """Prompt + result of every sibling-sweeper / engineering-loop call in the window."""
    now = time.time() if now is None else now
    if not root.is_dir():
        return []
    prompts: dict[str, str] = {}
    results: dict[str, str] = {}
    for f in root.rglob("*.jsonl"):
        try:
            if now - f.stat().st_mtime > WINDOW_S:
                continue
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line in lines:
            if '"tool_use"' not in line and '"tool_result"' not in line:
                continue
            try:
                content = (json.loads(line).get("message") or {}).get("content")
            except (json.JSONDecodeError, ValueError, AttributeError):
                continue
            for c in content if isinstance(content, list) else []:
                if not isinstance(c, dict):
                    continue
                inp = c.get("input") or {}
                if c.get("type") == "tool_use" and (
                        (c.get("name") in ("Agent", "Task")
                         and inp.get("subagent_type") == "sibling-sweeper")
                        or (c.get("name") == "Workflow"
                            and (inp.get("name") == "engineering-loop"
                                 or "engineering-loop" in str(inp.get("scriptPath", ""))))):
                    prompts[c.get("id", "")] = json.dumps(inp, ensure_ascii=False)
                elif c.get("type") == "tool_result":
                    results[c.get("tool_use_id", "")] = json.dumps(c.get("content"),
                                                                   ensure_ascii=False)
    return [p + "\n" + results.get(i, "") for i, p in prompts.items()]


def unbound(bodies: dict[str, str], texts: list[str]) -> list[str]:
    """Classes whose anchors appear in NO sweep text. Pure."""
    return sorted(cid for cid, body in bodies.items()
                  if not any(a in t for a in anchors(cid, body) for t in texts))


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


def main_git() -> int:
    """pre-commit mode (R186): the STAGED catalogue against HEAD — a `git commit` typed in a
    terminal is checked too. The index, not the working tree: pre-commit runs after staging.
    Without a transcript folder (CI, another machine) there is nothing to bind against: it
    says so and lets the commit through — the check lives where the sweeps are recorded."""
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                             text=True, timeout=10).stdout.strip()
        committed = subprocess.run(["git", "-C", top, "show", f"HEAD:{CATALOGUE}"],
                                   capture_output=True, text=True, timeout=20).stdout
        staged = subprocess.run(["git", "-C", top, "show", f":{CATALOGUE}"],
                                capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    if not added_entries(committed, staged):
        return 0
    tdir = transcripts_dir(Path(top))
    if not tdir.is_dir():
        print(f"▶ catalogue-sweep: no Claude Code transcripts at {tdir} — nothing to bind "
              "the new class to on this machine; not checked here.")
        return 0
    msg = verdict(added_entries(committed, staged), proof(tdir))
    loose = [] if msg else unbound(added_bodies(committed, staged), sweep_texts(tdir))
    if msg or loose:
        print(f"🚫 catalogue-sweep — {msg or ', '.join(loose) + ' : no sweep in the window mentions this class (id or cited file).'}"
              "\n   Spawn sibling-sweeper on it first. Escape, logged: SWEEP_OVERRIDE=<reason> in the environment.",
              file=sys.stderr)
        if os.environ.get("SWEEP_OVERRIDE"):
            log = Path(top) / ".claude" / "sessions" / "sweep-override.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as fh:
                fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} git-mode "
                         f"reason={os.environ['SWEEP_OVERRIDE']}\n")
            return 0
        return 1
    return 0


def main() -> int:
    if "--git" in sys.argv:
        return main_git()
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
        committed = subprocess.run(["git", "-C", top, "show", f"HEAD:{CATALOGUE}"],
                                   capture_output=True, text=True, timeout=20).stdout
        catalogue = Path(top) / CATALOGUE
        on_disk = catalogue.read_text(encoding="utf-8") if catalogue.exists() else ""
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return 0
    n = added_entries(committed, on_disk)
    if n == 0:
        return 0
    m = re.search(r"\bSWEEP_OVERRIDE=(\S+)", command)
    if m:
        log = Path(top) / ".claude" / "sessions" / "sweep-override.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} entries={n} reason={m.group(1)}\n")
        return 0
    tdir = transcripts_dir(Path(top))
    msg = verdict(n, proof(tdir))
    if msg is None:
        loose = unbound(added_bodies(committed, on_disk), sweep_texts(tdir))
        if not loose:
            return 0
        msg = (f"{', '.join(loose)} : aucun sibling-sweeper (ni engineering-loop) de la "
               "fenêtre ne mentionne cette classe — ni son id, ni un fichier qu'elle cite. "
               "Un balayage fait pour un AUTRE défaut ne prouve rien sur celui-ci : "
               "Spawn sibling-sweeper sur cette classe.")
    print(f"🚫 BLOCKED — {msg}\n   Échappatoire consignée : SWEEP_OVERRIDE=<raison> git commit …",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
