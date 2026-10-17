#!/usr/bin/env python3
"""Stop + SessionStart — commit when a roadmap task closes, push when the index reaches 0.
---
rex: []
---

Type: Hook
Uses: governance.toml ([roadmap] dir, index_title, id_prefix) or streamlytics' .claude/dev-docs/roadmap/
Persists in: .claude/sessions/roadmap-autocommit.json (session start snapshot + open ids),
             .claude/sessions/roadmap-autopush.log (the detached push and its exit code)
Triggers: git commit (hooks run), git push detached (hooks run), a systemMessage per action

Owner's request (2026-10-17): « automatiser les commit après avoir terminé une tâche en roadmap
puis dès qu'on a 0 tâche en roadmap on pousse de façon automatique ».

- `start` (SessionStart): records what is ALREADY dirty or untracked, so another session's
  leftovers are never swept into this session's commit.
- Stop: an id that left the checklist since the last turn is a closed task → commit the files
  this session touched (tracked, plus untracked created since start), message « T20 fermée ».
  Commit hooks run: a refused commit is reported, never forced (no --no-verify).
- Stop: the « Tâches ouvertes » table at 0 with commits ahead → `git push` detached (a pre-push
  gate may take 16 min), result shown at the next turn. Rows waiting on a human do not count:
  they would hold the push for days. Not only on the n > 0 → 0 transition (T25): a commit made
  once the index is already empty (a ROADMAP entry, a drift report) would otherwise stay ↑1.
  One push at a time; a HEAD whose push was refused is not retried (a red 16-min gate would
  rerun every turn); behind origin (↓n) it is reported, not attempted.

ROADMAP_AUTOCOMMIT=0 / ROADMAP_AUTOPUSH=0 turn each off. Never fails a turn.

guard_scope: the closed-id diff, the session snapshot filter, the index-only count, the push
decision and its three guards. NOT covered: two sessions closing tasks in the same repo at once (the second
commit takes what the first left).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path

# R365 (streamlytics): a hook leaves one trace line per run when the repo has _hook_trace.py; elsewhere a no-op.
sys.path.insert(0, str(Path(__file__).resolve().parent))
_trace = getattr(import_module("_hook_trace") if find_spec("_hook_trace") else None, "trace", lambda _path: None)
_trace(__file__)

STATE = Path(".claude/sessions/roadmap-autocommit.json")
PUSH_LOG = Path(".claude/sessions/roadmap-autopush.log")


def git(root: Path, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=timeout)


def config(root: Path) -> tuple[Path, str, str]:
    rdir, title, prefix = ".claude/dev-docs/roadmap", "## 📋 Tâches ouvertes", "R"
    toml = root / "governance.toml"
    if toml.is_file():
        import tomllib
        cfg = tomllib.loads(toml.read_text(encoding="utf-8")).get("roadmap", {})
        rdir = cfg.get("dir", "docs/roadmap")
        title, prefix = cfg.get("index_title", title), cfg.get("id_prefix", prefix)
    return root / rdir / "checklist.md", title, prefix


def all_ids(text: str, prefix: str) -> set[str]:
    """Every id in an index row, both tables — as roadmap_empty_beep counts them."""
    return set(re.findall(rf"^\|\s*({re.escape(prefix)}\d{{1,5}})\s*\|", text, re.M))


def index_ids(text: str, title: str, prefix: str) -> set[str]:
    """Ids of the open-tasks table only: from its heading to the next `## `."""
    start = next((i for i, ln in enumerate(text.splitlines()) if ln.startswith(title)), None)
    if start is None:
        return set()
    lines = text.splitlines()[start + 1:]
    end = next((i for i, ln in enumerate(lines) if ln.startswith("## ")), len(lines))
    return all_ids("\n".join(lines[:end]), prefix)


def dirty(root: Path) -> dict[str, str]:
    """path → content hash of every modified or untracked (not ignored) file."""
    out = git(root, "status", "--porcelain", "-z", "--untracked-files=all").stdout
    paths = [e[3:] for e in out.split("\0") if len(e) > 3]
    result = {}
    for p in paths:
        if p.startswith(".claude/sessions/"):  # this hook's own state, even where not gitignored
            continue
        f = root / p
        result[p] = hashlib.sha1(f.read_bytes()).hexdigest() if f.is_file() else ""
    return result


def touched(start: dict[str, str], now: dict[str, str]) -> list[str]:
    """What this session changed: dirty now and not dirty at start, or dirty at start but changed since."""
    return sorted(p for p, h in now.items() if start.get(p) != h)


def decide_push(last_index: int | None, now_index: int, ahead: int, behind: int = 0,
                pending: bool = False, head: str = "", refused: str | None = None) -> bool:
    """Index at 0, commits ahead, nothing to pull, no push in flight, HEAD not already refused."""
    return (last_index is not None and now_index == 0 and ahead > 0 and behind == 0
            and not pending and head != refused)


def load(root: Path) -> dict:
    try:
        return json.loads((root / STATE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(root: Path, state: dict) -> None:
    (root / STATE).parent.mkdir(parents=True, exist_ok=True)
    (root / STATE).write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def push_report(root: Path, state: dict) -> str | None:
    """The finished detached push, reported once."""
    log = root / PUSH_LOG
    if not state.get("push_pending") or not log.is_file():
        return None
    m = re.search(r"^rc=(\d+)$", log.read_text(encoding="utf-8", errors="replace"), re.M)
    if not m:
        return None
    state["push_pending"] = False
    if m.group(1) == "0":
        return "🚀 roadmap à 0 : push automatique réussi"
    state["refused_head"] = state.get("push_head")
    return f"⚠️ push automatique refusé (rc={m.group(1)}) — voir {PUSH_LOG}"


def start_push(root: Path) -> None:
    log = root / PUSH_LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = f'cd "{root}" && {{ date -Is; git push; echo "rc=$?"; }} > "{log}" 2>&1'
    subprocess.Popen(["bash", "-c", cmd], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def on_start(root: Path, session: str) -> None:
    state = load(root)
    if state.get("session") == session:  # a /resume keeps the original snapshot
        return
    state.update(session=session, start=dirty(root))
    save(root, state)


def on_stop(root: Path, session: str) -> list[str]:
    path, title, prefix = config(root)
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    state, msgs = load(root), []
    if report := push_report(root, state):
        msgs.append(report)
    if state.get("session") != session:  # SessionStart missed: snapshot now, act from next turn
        state.update(session=session, start=dirty(root))
    ids, idx = all_ids(text, prefix), index_ids(text, title, prefix)
    closed = sorted(set(state.get("open", [])) - ids)
    if closed and os.environ.get("ROADMAP_AUTOCOMMIT") != "0":
        now = dirty(root)
        files = touched(state.get("start", {}), now)
        if files:
            git(root, "add", "-A", "--", *files)
            msg = f"{', '.join(closed)} fermée{'s' if len(closed) > 1 else ''} — commit automatique"
            r = git(root, "commit", "-q", "-m", msg, "--", *files)
            if r.returncode == 0:
                msgs.append(f"✅ {msg} ({len(files)} fichier(s))")
                state["start"] = {p: h for p, h in state.get("start", {}).items() if p not in files}
            else:
                git(root, "reset", "-q", "--", *files)
                err = (r.stderr or r.stdout).strip().splitlines()
                msgs.append(f"⚠️ commit automatique refusé pour {', '.join(closed)} : {err[-1] if err else r.returncode}")
    if os.environ.get("ROADMAP_AUTOPUSH") != "0":
        r = git(root, "rev-list", "--left-right", "--count", "HEAD...@{u}")
        ahead, behind = map(int, r.stdout.split()) if r.returncode == 0 else (0, 0)
        head = git(root, "rev-parse", "HEAD").stdout.strip()
        if behind and ahead and not idx and state.get("behind_head") != head:
            state["behind_head"] = head
            msgs.append(f"⚠️ index à 0 mais ↓{behind} : pull avant le push automatique ({ahead} commit(s))")
        if decide_push(state.get("index"), len(idx), ahead, behind, bool(state.get("push_pending")),
                       head, state.get("refused_head")):
            start_push(root)
            state.update(push_pending=True, push_head=head)
            msgs.append(f"⏳ index à 0 : push automatique lancé ({ahead} commit(s)), résultat au prochain tour")
    state.update(open=sorted(ids), index=len(idx))
    save(root, state)
    return msgs


def main(argv: list[str]) -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        payload = {}
    session = payload.get("session_id", "")
    out = git(Path.cwd(), "rev-parse", "--show-toplevel")
    if out.returncode != 0:
        return 0
    root = Path(out.stdout.strip())
    if len(argv) > 1 and argv[1] == "start":
        on_start(root, session)
        return 0
    if msgs := on_stop(root, session):
        print(json.dumps({"systemMessage": " · ".join(msgs)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception:  # noqa: BLE001 — automation never blocks the end of a turn
        sys.exit(0)
