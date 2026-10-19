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
- Stop: the `reprise:` anchor is rewritten from the index first (T34), so it never lies.
- Stop: an id that left the checklist since the last turn is a closed task → commit the files
  this session touched (tracked, plus untracked created since start), message « T20 fermée ».
  Commit hooks run: a refused commit is reported, never forced (no --no-verify).
- Stop: the « Tâches ouvertes » table at 0 with commits ahead → `git push` detached (a pre-push
  gate may take 16 min), result shown at the next turn. Rows waiting on a human do not count:
  they would hold the push for days. Not only on the n > 0 → 0 transition (T25): a commit made
  once the index is already empty (a ROADMAP entry, a drift report) would otherwise stay ↑1.
  One push at a time; a HEAD whose push was refused is not retried (a red 16-min gate would
  rerun every turn); behind origin (↓n) it is reported, not attempted. A branch WITHOUT
  upstream but with a remote is counted against that remote and SAID once per HEAD (« pas
  d'amont », the `push -u` to make): creating a remote branch is not done for the owner.

- Stop + SessionStart (T159), the fleet master only (tools/dev/fleet_apply.py present): a HEAD
  equal to its upstream that no apply has stamped (state/fleet-history.jsonl, `source: apply`)
  launches `fleet_apply.py apply --push` detached — a MANUAL `git push` never did. At most once
  per HEAD (`launched_head`, written before the spawn), never while a push is pending, never
  while an apply holds state/fleet-apply.lock, never from a linked worktree. A failed apply is
  retried only by the cron or the next HEAD. ROADMAP_AUTOAPPLY=0 turns it off.

- Stop (T82): a task closed while its CI was not read yet (`ci-pending.json` beside the
  checklist) has it read by `roadmap.py ci` at most every 5 min: green, forgotten; red, the task
  is back in the index and said. Without it no task closed in a repo with CI before a manual push.

- T158 (2026-10-19): `.claude/worktrees/` (the harness' agent worktrees) is never swept in: it was
  in no ignore list, a new worktree came out of `git status` as `?? .claude/worktrees/wf_x/` and
  `git add -A` staged it as a gitlink — 4 automatic commits of the master carried 9 of them and a
  9 759-line .diff. Submodules are read with `--ignore-submodules=all`, as session_closable does.
- T158: a HEAD whose push was refused is said once per (HEAD, rc), and retried when the LAST rc of
  the log is 0 again. Its producer is the hand: the gate rerun after the fix, then
  `echo rc=0 >> .claude/sessions/roadmap-autopush.log` (the beep says so). The retried push goes
  through the pre-push gate again — a wrong `rc=0` costs a gate run, never an ungated push.

ROADMAP_AUTOCOMMIT=0 / ROADMAP_AUTOPUSH=0 turn each off. Never fails a turn.

guard_scope: the closed-id diff, the session snapshot filter, the index-only count, the push
decision and its three guards, the « pas d'amont » notice and its remote resolution. NOT covered: two sessions closing tasks in the same repo at once (the second
commit takes what the first left).
"""
from __future__ import annotations

import hashlib
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path

# R365 (streamlytics): a hook leaves one trace line per run when the repo has _hook_trace.py; elsewhere a no-op.
sys.path.insert(0, str(Path(__file__).resolve().parent))
_trace = getattr(import_module("_hook_trace") if find_spec("_hook_trace") else None, "trace", lambda _path: None)
_trace(__file__)

STATE = Path(".claude/sessions/roadmap-autocommit.json")
PUSH_LOG = Path(".claude/sessions/roadmap-autopush.log")
NEVER_SWEPT = (".claude/sessions/", ".claude/worktrees/")  # this hook's state; the agents' worktrees (T158)
APPLY = "tools/dev/fleet_apply.py"  # only the fleet master has it (T66)
APPLY_HISTORY = "state/fleet-history.jsonl"  # fleet_apply's readings; `source: apply` rows carry the HEAD (T159)
APPLY_LOCK = "state/fleet-apply.lock"
APPLY_LOG = Path(".claude/sessions/fleet-apply.log")
ROADMAP_TOOL = "tools/governance/roadmap.py"
CI_EVERY_S = 300


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


_ANCHOR = re.compile(r"<!--\s*reprise:\s*open=([^>]*?)\s*-->")


def sync_anchor(text: str, prefix: str) -> str:
    """T34: the `<!-- reprise: open=… -->` anchor rewritten from the index rows (both tables),
    as `roadmap.py sync` does. A row added by hand left it stale until the next close. A
    checklist without the anchor is left as it is."""
    ids = list(dict.fromkeys(re.findall(rf"^\|\s*({re.escape(prefix)}\d{{1,5}})\s*\|", text, re.M)))
    return _ANCHOR.sub(f"<!-- reprise: open={', '.join(ids)} -->", text, count=1)


def dirty(root: Path) -> dict[str, str]:
    """path → content hash of every modified or untracked (not ignored) file. A submodule or a
    nested repo is never one: committed, it is a gitlink (T158)."""
    out = git(root, "status", "--porcelain", "-z", "--untracked-files=all", "--ignore-submodules=all").stdout
    paths = [e[3:] for e in out.split("\0") if len(e) > 3]
    result = {}
    for p in paths:
        if p.startswith(NEVER_SWEPT):  # even where not gitignored
            continue
        f = root / p
        result[p] = hashlib.sha1(f.read_bytes()).hexdigest() if f.is_file() else ""
    return result


def touched(start: dict[str, str], now: dict[str, str]) -> list[str]:
    """What this session changed: dirty now and not dirty at start, or dirty at start but changed since."""
    return sorted(p for p, h in now.items() if start.get(p) != h)


def push_remote(root: Path) -> str | None:
    """The remote a push goes to, in git's order: branch.<b>.pushRemote, remote.pushDefault,
    branch.<b>.remote, the only remote, else `origin`. None: no remote at all. Same table as the
    master's tools/dev/git_upstream.py — a hook cannot import it; test_git_upstream.py runs both."""
    remotes = git(root, "remote").stdout.split()
    if not remotes:
        return None
    branch = git(root, "symbolic-ref", "--short", "-q", "HEAD").stdout.strip()
    keys = ([f"branch.{branch}.pushRemote"] if branch else []) + ["remote.pushDefault"] + \
        ([f"branch.{branch}.remote"] if branch else [])
    for key in keys:
        v = git(root, "config", "--get", key).stdout.strip()
        if v in remotes:
            return v
    return remotes[0] if len(remotes) == 1 else "origin"


def ahead_of_remote(root: Path, remote: str) -> int | None:
    """Commits of HEAD the remote holds under no branch — what `push -u <remote> HEAD` would
    carry. None when unreadable: never folded into 0, the fault this replaces."""
    r = git(root, "rev-list", "--count", "HEAD", "--not", f"--remotes={remote}")
    return int(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


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


def last_rc(root: Path) -> str | None:
    """The LAST `rc=` of the push log — a gate rerun by hand appends `rc=0` after a refusal."""
    log = root / PUSH_LOG
    rcs = re.findall(r"^rc=(\d+)$", log.read_text(encoding="utf-8", errors="replace"), re.M) if log.is_file() else []
    return rcs[-1] if rcs else None


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
    state["refused_said"] = f"{state.get('push_head')}:{m.group(1)}"
    return f"⚠️ push automatique refusé (rc={m.group(1)}) — voir {PUSH_LOG}"


def refused_notice(root: Path, state: dict, head: str) -> str | None:
    """T158: while HEAD is the refused one, the refusal is said once per (HEAD, rc) — never by
    rerunning the 16-min gate. The last rc back at 0 (written by hand after the gate passed)
    lifts the refusal: decide_push retries, and the push passes the gate again."""
    if state.get("push_pending") or not head or state.get("refused_head") != head:
        return None
    rc = last_rc(root)
    if rc == "0":
        state["refused_head"] = None
        return None
    if rc is None or state.get("refused_said") == f"{head}:{rc}":
        return None
    state["refused_said"] = f"{head}:{rc}"
    return (f"⚠️ push refusé par le gate (rc={rc}) sur {head[:7]} — corrige puis relance : un commit le "
            f"retente, ou la porte repassée puis `echo rc=0 >> {PUSH_LOG}`")


def start_push(root: Path) -> None:
    log = root / PUSH_LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    # The fleet master pushed → the fleet is reconciled right after (T66): a validated change
    # reaches every `managed` repo without a second gesture. Elsewhere the file is absent.
    cmd = (f'cd "{root}" && {{ date -Is; git push; rc=$?; echo "rc=$rc"; }} > "{log}" 2>&1; '
           f'[ "$rc" = 0 ] && [ -f {APPLY} ] && python3 {APPLY} apply --push >> "{log}" 2>&1')
    subprocess.Popen(["bash", "-c", cmd], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def last_applied_head(root: Path) -> str | None:
    """The master HEAD of the last `source: apply` row — the tail only, the file grows daily."""
    try:
        with (root / APPLY_HISTORY).open("rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 256_000))
            tail = f.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in reversed(tail):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("source") == "apply":
            return row.get("head")
    return None


def apply_running(root: Path) -> bool:
    lock = root / APPLY_LOCK
    if not lock.is_file():
        return False
    with lock.open("a") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fh, fcntl.LOCK_UN)
    return False


def start_apply(root: Path) -> None:
    log = root / APPLY_LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = f'cd "{root}" && {{ date -Is; python3 {APPLY} apply --push; echo "rc=$?"; }} > "{log}" 2>&1'
    subprocess.Popen(["bash", "-c", cmd], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def maybe_apply(root: Path, state: dict) -> str | None:
    """T159: the master at its upstream, on a HEAD no apply has seen → apply, once per HEAD."""
    if not (root / APPLY).is_file() or "0" in (os.environ.get("ROADMAP_AUTOAPPLY"), os.environ.get("ROADMAP_AUTOPUSH")):
        return None
    if git(root, "rev-parse", "--git-dir").stdout.strip() != git(root, "rev-parse", "--git-common-dir").stdout.strip():
        return None  # a linked worktree: its HEAD is not the master's
    head = git(root, "rev-parse", "HEAD").stdout.strip()
    up = git(root, "rev-parse", "@{u}")
    if not head or up.returncode or up.stdout.strip() != head:
        return None
    if state.get("push_pending") or state.get("launched_head") == head:
        return None  # a push in flight runs its own apply; this HEAD was launched already
    if last_applied_head(root) == head or apply_running(root):
        return None
    state["launched_head"] = head  # before the spawn: two Stops never launch twice
    save(root, state)
    start_apply(root)
    return f"⏳ HEAD {head[:7]} jamais appliqué au parc : fleet_apply.py apply --push lancé ({APPLY_LOG})"


def ci_report(root: Path, checklist: Path, state: dict, now: float) -> str | None:
    """The CIs of the tasks closed in wait (T82), read at most every CI_EVERY_S."""
    if not (checklist.parent / "ci-pending.json").is_file() or not (root / ROADMAP_TOOL).is_file():
        return None
    if now - state.get("ci_at", 0) < CI_EVERY_S:
        return None
    state["ci_at"] = now
    try:
        r = subprocess.run([sys.executable, str(root / ROADMAP_TOOL), "ci"], cwd=str(root),
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    said = " · ".join(ln for ln in (r.stdout + r.stderr).splitlines() if ln.startswith(("✅", "❌")))
    return said or None


def on_start(root: Path, session: str) -> None:
    state = load(root)
    if state.get("session") == session:  # a /resume keeps the original snapshot
        return
    state.update(session=session, start=dirty(root))
    save(root, state)
    maybe_apply(root, state)


def on_stop(root: Path, session: str) -> list[str]:
    path, title, prefix = config(root)
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    if (synced := sync_anchor(text, prefix)) != text:
        path.write_text(synced, encoding="utf-8")
        text = synced
    state, msgs = load(root), []
    if report := push_report(root, state):
        msgs.append(report)
    if report := ci_report(root, path, state, time.time()):
        msgs.append(report)
        text = path.read_text(encoding="utf-8")  # a red CI put its task back in the index
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
        upstream = r.returncode == 0
        remote = None if upstream else push_remote(root)
        head = git(root, "rev-parse", "HEAD").stdout.strip()
        if upstream:
            ahead, behind = map(int, r.stdout.split())
            if note := refused_notice(root, state, head):
                msgs.append(note)
            if behind and ahead and not idx and state.get("behind_head") != head:
                state["behind_head"] = head
                msgs.append(f"⚠️ index à 0 mais ↓{behind} : pull avant le push automatique ({ahead} commit(s))")
            if decide_push(state.get("index"), len(idx), ahead, behind, bool(state.get("push_pending")),
                           head, state.get("refused_head")):
                start_push(root)
                state.update(push_pending=True, push_head=head, launched_head=head)
                msgs.append(f"⏳ index à 0 : push automatique lancé ({ahead} commit(s)), résultat au prochain tour")
        elif remote:
            # rc 128 is « no upstream », not « nothing to push » (read as 0 ahead until 2026-10-18:
            # the push never fired and nothing was said). Creating a remote branch is a new
            # outward gesture (rule 5): it is SAID once per HEAD, never done.
            n = ahead_of_remote(root, remote)
            if (decide_push(state.get("index"), len(idx), 1 if n is None else n)
                    and state.get("no_upstream_head") != head):
                state["no_upstream_head"] = head
                msgs.append(f"⚠️ index à 0 mais pas d'amont : {'?' if n is None else n} commit(s) non "
                            f"poussé(s) — `git push -u {remote} HEAD` à faire à la main")
    if report := maybe_apply(root, state):
        msgs.append(report)
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
