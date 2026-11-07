#!/usr/bin/env python3
"""Stop + SessionStart — commit when a roadmap task closes, push when the index reaches 0.
---
rex: []
---

Type: Hook
Uses: governance.toml ([roadmap] dir, index_title, id_prefix) or streamlytics' .claude/dev-docs/roadmap/
Persists in: .claude/sessions/roadmap-autocommit.json (session start snapshot + open ids),
             .claude/sessions/roadmap-autopush.log (the detached push and its exit code),
             .claude/sessions/roadmap-autopush-history.log (APPENDED: one `rc=N head=H` per push — the
             log above is overwritten by the next push, the journal never is)
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

- T653 (2026-11-03): a refusal is no longer said only by a `systemMessage` (shown to the owner, read by
  neither the model nor a Stop gate). A refused push, a refused automatic commit and a failed apply
  put a ROW back at the head of « Tâches ouvertes » (`<!-- défaut -->`, `<!-- motif: … -->`, the three
  plain fields): the open row blocks the Stop (todo_gate) and the index is no longer 0, so no push
  loop. ONE row per motif: a second refusal completes the open row, it adds none. The row is closed
  by the normal `roadmap.py close` (a proof), never by this hook. The systemMessage stays.

- T682 (2026-11-05): the automatic commit no longer dies on a TRANSIENT git lock. `git add` and `git commit`
  share one bounded retry (COMMIT_LOCK_WAIT_S, well under the Stop hook's 120 s timeout), retried ONLY when
  git's own `fatal:/error:` line matches LOCKED (a copy of tools/dev/commit_readings.LOCKED — the hook is
  deployed where tools/dev is not; a test pins the two equal). A hook refusal (pre-commit) is never retried,
  never forced. The add's rc is read. The WHOLE refusal text is APPENDED to REFUSAL_JOURNAL (bounded); the
  message and the row carry the line that names the cause, not blindly the last one.
- T686 (2026-11-05): (a) a push is not launched while a local CI run (ci_local.sh) runs under THIS repo
  (it rm's its stamp at its start: the pre-push --check would refuse the push). Not a refusal: the next Stop
  retries; after CI_WAIT_MAX_STOPS Stops the wait is given up and said. The detection is RACY (a ci-local
  started after the check is not seen): the pre-push --check stays the real guard. (b) the hook does not dirty
  the TRACKED checklist while a gate judges the tree: a refusal row raised while a push or a ci-local is in
  flight is parked in the state (`pending_refusals`, and journalled), flushed at the top of the next Stop
  before anything reads the checklist, and the Stop is BLOCKED while it is parked (T653 holds). The `reprise:`
  anchor is no longer rewritten ahead of a push: it is written at the end of the Stop, and not when a push
  was launched or a gate is in flight.

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
PUSH_HISTORY = Path(".claude/sessions/roadmap-autopush-history.log")  # appended, never overwritten (T653)
REFUSAL_JOURNAL = Path(".claude/sessions/roadmap-autocommit-refusals.log")  # APPENDED, trimmed to the last MAX bytes (T682)
REFUSAL_JOURNAL_MAX = 64_000
# A copy of tools/dev/commit_readings.LOCKED: the hook ships to repos without tools/dev, so it cannot import it.
# test_the_lock_regex_equals_the_one_of_commit_readings pins the copies equal.
LOCKED = re.compile(r"index\.lock|cannot lock ref|Unable to create .*\.lock")
# Both in seconds. The whole on_stop has a 120 s hook timeout (settings.json) and also pushes, reads CI and applies:
# the retry shares ONE deadline across add and commit and stays far below it, or the harness kills the hook mid-flight.
COMMIT_LOCK_WAIT_S = 20.0
COMMIT_LOCK_STEP_S = 1.0
CI_WAIT_MAX_STOPS = 40  # T686a: Stops a running ci-local may hold the push back before the wait is given up
STALE_PUSH_S = 2 * 3600  # T282: the gate takes ~16 min; a log frozen this long has no live push


def _owner():
    """THIS repo's tools/governance/config.py (the one owner of the run-time files), or None where it has none."""
    from importlib.util import module_from_spec, spec_from_file_location
    path = Path(__file__).resolve().parents[2] / "tools/governance/config.py"
    try:
        spec = spec_from_file_location("roadmap_autocommit_gov_config", path)
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:  # absent or broken: the fallbacks below carry the same values, the hook must not stop
        return None


_GOV = _owner()
# tools/governance's run-time files (config.RUNTIME_FILES), under a roadmap.dir that varies per repo:
# matched by NAME, even where .gitignore is not repaired yet (a swept ci-pending.json is committed)
NEVER_SWEPT_NAMES = tuple(getattr(_GOV, "RUNTIME_FILES", ("ci-pending.json",)))
# …and the root run-time directories (config.ROOT_RUNTIME_DIRS: state/kpi.json…), matched by PREFIX for the
# same reason. The fallback is the owner's value where a repo ships this hook without tools/governance;
# test_governance_state_is_never_committable pins both to config.
NEVER_SWEPT = (".claude/sessions/", ".claude/worktrees/",  # this hook's state; the agents' worktrees (T158)
               *getattr(_GOV, "ROOT_RUNTIME_DIRS", ("state/",)))
APPLY = "tools/dev/fleet_apply.py"  # only the fleet master has it (T66)
APPLY_HISTORY = "state/fleet-history.jsonl"  # fleet_apply's readings; `source: apply` rows carry the HEAD (T159)
APPLY_LOCK = "state/fleet-apply.lock"
APPLY_LOG = Path(".claude/sessions/fleet-apply.log")
DEFER_RETRY_S = 600  # T613: an apply deferred by a live session elsewhere is relaunched by a Stop at most this often
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


def closed_this_turn(root: Path, checklist: Path, prefix: str, ids: set[str]) -> set[str]:
    """T800: rows whose archive entry is added but not committed and whose row is gone. `state["open"]`
    is read at Stop, so a row opened AND closed between two Stops never entered it: nothing was
    committed and the push left on a dirty tree (f08b5326, refused by the generated-files gate)."""
    archive = checklist.parent / "archive.md"
    r = git(root, "diff", "HEAD", "--unified=0", "--", str(archive))
    added = re.findall(rf"^\+- \[[xX]\] \*\*({re.escape(prefix)}\d{{1,5}})\b", r.stdout, re.M)
    return set(added) - ids


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
    out = git(root, "--no-optional-locks", "status", "--porcelain", "-z", "--untracked-files=all", "--ignore-submodules=all").stdout
    paths = [e[3:] for e in out.split("\0") if len(e) > 3]
    result = {}
    for p in paths:
        if p.startswith(NEVER_SWEPT) or p.rsplit("/", 1)[-1] in NEVER_SWEPT_NAMES:  # even where not gitignored
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
                pending: bool = False, head: str = "", refused: str | None = None,
                ci_running: bool = False) -> bool:
    """Index at 0, commits ahead, nothing to pull, no push in flight, HEAD not already refused, and no
    ci-local running (T686a: it removed its stamp, the pre-push --check would refuse; the next Stop retries)."""
    return (last_index is not None and now_index == 0 and ahead > 0 and behind == 0
            and not pending and head != refused and not ci_running)


def ci_local_running(root: Path, proc: str = "/proc") -> bool:
    """T686a: a local CI run (`ci_local.sh`) of THIS repo is running. A process counts only when its argv[0]
    is a shell or make (not an editor, grep or pgrep naming the script), it runs ci_local.sh or `ci-local`, its
    cwd is under `root`, and it is neither this hook nor its parent. An unreadable /proc entry is « not running »
    and said on stderr. RACY by construction: a ci-local started after this look is not seen — the pre-push
    `ci_local.sh --check` remains the real guard."""
    skip, here = {os.getpid(), os.getppid()}, str(root.resolve())
    try:
        entries = [e for e in os.listdir(proc) if e.isdigit()]
    except OSError as exc:
        print(f"roadmap_autocommit: {proc} unreadable ({exc}), ci-local taken as not running", file=sys.stderr)
        return False
    for pid in entries:
        if int(pid) in skip:
            continue
        try:
            argv = [x.decode("utf-8", "replace") for x in (Path(proc) / pid / "cmdline").read_bytes().split(b"\0") if x]
            if not argv or Path(argv[0]).name not in ("bash", "sh", "dash", "zsh", "make", "gmake"):
                continue
            if not any(Path(x).name == "ci_local.sh" or x == "ci-local" for x in argv[1:]):
                continue
            cwd = os.readlink(Path(proc) / pid / "cwd")
        except OSError as exc:  # PermissionError, ProcessLookupError, FileNotFoundError: gone or not ours
            print(f"roadmap_autocommit: {proc}/{pid} unreadable ({exc.__class__.__name__}), taken as not running",
                  file=sys.stderr)
            continue
        if cwd == here or cwd.startswith(here + os.sep):
            return True
    return False


def gate_in_flight(root: Path, state: dict) -> bool:
    """T686b: a push (its pre-push gate) or a ci-local is judging the working tree right now."""
    return bool(state.get("push_pending")) or ci_local_running(root)


def load(root: Path) -> dict:
    try:
        return json.loads((root / STATE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(root: Path, state: dict) -> None:
    (root / STATE).parent.mkdir(parents=True, exist_ok=True)
    (root / STATE).write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def last_rc(root: Path) -> str | None:
    """The LAST `rc=` of the push log — a gate rerun by hand appends `rc=0` after a refusal. The log is
    overwritten by the next push: with none in it (a push in flight), the journal's last push answers (T653)."""
    log, hist = root / PUSH_LOG, root / PUSH_HISTORY
    rcs = re.findall(r"^rc=(\d+)$", log.read_text(encoding="utf-8", errors="replace"), re.M) if log.is_file() else []
    if not rcs and hist.is_file():
        rcs = re.findall(r"^rc=(\d+) head=", hist.read_text(encoding="utf-8", errors="replace"), re.M)
    return rcs[-1] if rcs else None


def _last_verdict(key: str, *files: Path) -> str:
    """T782: a closure measure that CAN fail. `tail -1` of a file exits 0 whatever it reads — and the journal's
    last line is an `apply_rc=` after a green push, so it never held the push's `rc=`. This keeps the values of
    the lines starting with `key=` over the files in order (the later file wins, as `last_rc` reads the log after
    the journal; a missing file is skipped: a push overwrites the log) and exits 0 only if the last one is 0; no
    such line is a failure too. No pipe: the measure sits in a table cell."""
    names = " ".join(str(f) for f in files)
    return f"v=$(echo $(sed -En 's/^{key}=([0-9]+).*/\\1/p' {names} 2>/dev/null)); test \"${{v##* }}\" = 0"


# T653 — a refusal reopens a row: the only channel a Stop gate reads is the open index.
MOTIFS = {
    "push-refusé": (
        "Défaut — le push automatique du dernier commit a été refusé par la porte",
        "le contrôle fait avant l'envoi a échoué ; l'envoi n'a pas eu lieu et seul un message, que ni toi ni "
        "la séance ne relisent, le disait",
        "le journal des envois automatiques se termine par un succès",
        "la séance corrige la cause, relance le contrôle, puis ferme cette ligne ; l'envoi repart ensuite tout seul",
        f"`{_last_verdict('rc', PUSH_HISTORY, PUSH_LOG)}` sort à 0"),
    "commit-refusé": (
        "Défaut — le commit automatique d'une tâche fermée a été refusé",
        "le contrôle fait avant l'enregistrement a échoué ; les fichiers de la tâche restent non enregistrés "
        "et seul un message le disait",
        "un enregistrement de la tâche existe et l'arbre n'a plus de fichier à elle en attente",
        "la séance corrige ce que le contrôle refuse, enregistre elle-même, puis ferme cette ligne",
        "`test -z \"$(git status --short)\"` sort à 0 (l'arbre n'a plus de fichier en attente)"),
    "apply-échoué": (
        "Défaut — le déploiement automatique sur le parc a échoué",
        "la commande qui répand la configuration validée est sortie en échec et seul un fichier de trace, "
        "que personne ne relit, le disait",
        "la dernière ligne `apply_rc=` du journal des envois automatiques est un succès",
        "la séance lit le journal (le détail est dans roadmap-autopush.log), corrige, relance le déploiement, "
        "puis ferme cette ligne",
        f"`{_last_verdict('apply_rc', PUSH_HISTORY)}` sort à 0"),
}


def next_id(checklist: Path, text: str, prefix: str) -> str:
    """The first id above every one the checklist AND its archive ever held."""
    seen = [text]
    archive = checklist.parent / "archive.md"
    if archive.is_file():
        seen.append(archive.read_text(encoding="utf-8", errors="replace"))
    nums = [int(n) for t in seen for n in re.findall(rf"\b{re.escape(prefix)}(\d{{1,5}})\b", t)]
    return f"{prefix}{max(nums, default=0) + 1}"


REFUSAL_REQ = "REQ-GOV-43"  # T679: the requirement a refusal row serves, where the repo's catalogue holds it


def trace_tags(root: Path) -> str:
    """T679: the `exigence` and `livrable` a gate demands of every open row (requirements_trace,
    deliverables). Without them the next pre-push gate went red on the very row that said the push was
    refused, and the push never came back (T678, 2026-11-03). A repo whose catalogue lacks
    REFUSAL_REQ gets `aucune — <raison>`: close refuses an unknown id."""
    try:
        known = f"id: {REFUSAL_REQ}" in (root / "docs/architecture/requirements.yaml").read_text(encoding="utf-8")
    except OSError:
        known = False
    req = REFUSAL_REQ if known else "aucune — défaut rouvert par le hook, sa cause est corrigée sous sa propre ligne"
    return f"<!-- exigence: {req} --> <!-- livrable: .claude/hooks/roadmap_autocommit.py -->"


def reopen_refusal(root: Path, motif: str, detail: str, state: dict | None = None) -> bool:
    """T653: a refusal said where a gate reads it — a `<!-- défaut -->` row at the head of the index.
    One row per `motif`: while one is open, a new `detail` is appended to it, never a second row. True
    when the checklist changed. Needs no roadmap.py (a repo of the fleet may lack it): pure text.
    T686b: with a `state` and a gate in flight (a push, a ci-local) the TRACKED checklist is not written — it
    would dirty the tree the gate judges. The refusal is parked in `state['pending_refusals']` (and journalled,
    in case the state is lost) and flushed by the next Stop; False."""
    if state is not None and gate_in_flight(root, state):
        parked = state.setdefault("pending_refusals", [])
        if [motif, detail] not in parked:
            parked.append([motif, detail])
            journal_refusal(root, f"PARKED {motif}", detail)
        return False
    path, title, prefix = config(root)
    if not path.is_file() or motif not in MOTIFS:
        return False
    detail = detail.replace("|", "/").replace("-->", "->")
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    start = next((i for i, ln in enumerate(lines) if ln.startswith(title)), None)
    if start is None:
        return False
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    mark = f"<!-- motif: {motif} -->"
    for i in range(start + 1, end):
        if mark in lines[i]:
            if detail in lines[i]:
                return False
            lines[i] = lines[i].replace(mark, f"; aussi {detail} {mark}", 1)
            path.write_text(sync_anchor("".join(lines), prefix), encoding="utf-8")
            return True
    sep = next((i for i in range(start + 1, end) if re.match(r"^\|\s*:?-{3,}", lines[i])), None)
    if sep is None:
        return False
    what, cause, guard, integ, measure = MOTIFS[motif]
    row = (f"| {next_id(path, text, prefix)} | {what} ({detail}) <!-- défaut --> {mark} {trace_tags(root)} "
           f"<!-- cause: {cause} --> <!-- garde: {guard} --> <!-- intégration: {integ} --> | P1 | {measure} |\n")
    lines.insert(sep + 1, row)
    path.write_text(sync_anchor("".join(lines), prefix), encoding="utf-8")
    return True


def _keep_always(root: Path, state: dict, detail: str) -> bool:
    return True


def _push_refusal_holds(root: Path, state: dict, detail: str) -> bool:
    """« <head7> rc=N » holds until THAT head is seen back at rc=0: the journal's last row for the head, or
    (a gate rerun by hand: `echo rc=0 >> log`) the log's last rc while the log is the one of that head. A bare
    last_rc() is not enough: it falls back to the journal and can answer for another push. Unknown → keep."""
    m = re.match(r"(\w+) rc=\d+", detail)
    if not m:
        return True
    h7, hist = m.group(1)[:7], root / PUSH_HISTORY
    if hist.is_file():
        rows = [rc for rc, h in re.findall(r"^rc=(\d+) head=(\w+)", hist.read_text(encoding="utf-8", errors="replace"), re.M)
                if h.startswith(h7)]
        if rows and rows[-1] == "0":
            return False
    log = root / PUSH_LOG
    log_rcs = re.findall(r"^rc=(\d+)$", log.read_text(encoding="utf-8", errors="replace"), re.M) if log.is_file() else []
    if log_rcs and log_rcs[-1] == "0" and str(state.get("push_head") or "").startswith(h7) and not state.get("push_pending"):
        return False  # the LOG only (never last_rc's journal fallback): it is the log of state['push_head']
    return True


def _apply_refusal_holds(root: Path, state: dict, detail: str) -> bool:
    """Holds while apply_failure() reports ANY failure, whatever its value: a failure that moved (rc=86 → 87,
    another head, the legacy trace) is still a failure — only the journal back at apply_rc=0 lifts the refusal."""
    return apply_failure(root) is not None


# motif → « does the source still say so? ». commit-refusé and any motif without a reader default to KEEP
# (fail-closed toward writing); test_every_motif_has_a_park_check keeps a new motif from taking the default silently.
PARK_CHECKS = {"push-refusé": _push_refusal_holds, "apply-échoué": _apply_refusal_holds, "commit-refusé": _keep_always}


def prune_parked(root: Path, state: dict) -> int:
    """A parked refusal is a value read EARLIER: dropped (journalled DROPPED) when its source no longer says
    it. Pure on `state`, runs even while a gate is in flight (the Stop block reads the same list). Number dropped."""
    parked = state.get("pending_refusals") or []
    kept = [[m, d] for m, d in parked if PARK_CHECKS.get(m, _keep_always)(root, state, d)]
    for m, d in parked:
        if [m, d] not in kept:
            journal_refusal(root, f"DROPPED {m}", d)
    if apply_failure(root) is None:
        state.pop("apply_failed_said", None)  # a later recurrence of the same « head apply rc=N » must be said again
    if len(kept) != len(parked):
        state["pending_refusals"] = kept
    return len(parked) - len(kept)


def flush_refusals(root: Path, state: dict) -> tuple[int, int]:
    """T686b: the parked refusals written to the checklist once no gate is in flight, each re-checked against its
    source first. (rows really written, rows dropped as no longer true)."""
    dropped = prune_parked(root, state)
    parked = state.get("pending_refusals") or []
    if not parked or gate_in_flight(root, state):
        return 0, dropped
    written = sum(bool(reopen_refusal(root, motif, detail)) for motif, detail in parked)
    state["pending_refusals"] = []
    return written, dropped


def journal_refusal(root: Path, title: str, text: str) -> None:
    """T682: the whole refusal APPENDED (never overwritten), the file trimmed to its last REFUSAL_JOURNAL_MAX bytes."""
    path = root / REFUSAL_JOURNAL
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%dT%H:%M:%S%z')} {title}\n{text.rstrip()}\n")
        if path.stat().st_size > REFUSAL_JOURNAL_MAX:
            path.write_bytes(path.read_bytes()[-REFUSAL_JOURNAL_MAX:])
    except OSError:
        pass  # a journal that cannot be written must not cost the commit's own report


def is_lock_refusal(text: str) -> bool:
    """git's OWN lock error: a `fatal:`/`error:` line matching LOCKED. A pre-commit hook that merely prints
    « index.lock » is a refusal, not a lock — it is never retried."""
    return any(LOCKED.search(ln) and re.match(r"\s*(fatal|error):", ln) for ln in text.splitlines())


def refusal_summary(text: str) -> str:
    """The line that names the cause: the LOCKED one, else the first « error / hook / fatal » line, else the last."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines:
        if LOCKED.search(ln):
            return ln
    for ln in lines:
        if re.search(r"error|hook|fatal", ln, re.I):
            return ln
    return lines[-1] if lines else ""


def commit_with_retry(root: Path, files: list[str], msg: str, wait_s: float | None = None,
                      step_s: float | None = None) -> subprocess.CompletedProcess:
    """T682: `git add -A` then `git commit`, retried while git's own lock error clears, ONE deadline for both.
    The add's rc is read (a failed add never reaches the commit). Anything else — a hook refusal above all —
    is returned at once. The returned process carries the stage that failed in `.stage`."""
    wait = COMMIT_LOCK_WAIT_S if wait_s is None else wait_s
    step = COMMIT_LOCK_STEP_S if step_s is None else step_s
    deadline = time.monotonic() + wait
    while True:
        r = git(root, "add", "-A", "--", *files)
        r.stage = "add"
        if r.returncode == 0:
            r = git(root, "commit", "-q", "-m", msg, "--", *files)
            r.stage = "commit"
        if r.returncode == 0 or not is_lock_refusal((r.stderr or "") + (r.stdout or "")) \
                or time.monotonic() + step > deadline:
            return r
        time.sleep(step)


def push_dead(state: dict, log: Path, now: float | None = None) -> bool:
    """The detached push is gone: its pid no longer runs, or — no pid kept — its log froze > 2 h."""
    pid = state.get("push_pid")
    if pid:
        return not Path(f"/proc/{pid}").exists()
    return (now or time.time()) - log.stat().st_mtime > STALE_PUSH_S


def push_report(root: Path, state: dict) -> str | None:
    """The finished detached push, reported once."""
    log = root / PUSH_LOG
    if not state.get("push_pending") or not log.is_file():
        return None
    m = re.search(r"^rc=(\d+)$", log.read_text(encoding="utf-8", errors="replace"), re.M)
    if not m:
        # T282: a push killed before its `rc=` (WSL stopped mid-gate) held `push_pending` for good and
        # every later push with it, silently. Dead → said once and released, its HEAD NOT refused.
        if not push_dead(state, log):
            return None
        state["push_pending"] = False
        return f"⚠️ push automatique mort sans verdict ({PUSH_LOG}) — relancé au prochain tour"
    state["push_pending"] = False
    if m.group(1) == "0":
        return "🚀 roadmap à 0 : push automatique réussi"
    state["refused_head"] = state.get("push_head")
    state["refused_said"] = f"{state.get('push_head')}:{m.group(1)}"
    reopen_refusal(root, "push-refusé", f"{str(state.get('push_head') or '?')[:7]} rc={m.group(1)}", state)
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
    reopen_refusal(root, "push-refusé", f"{head[:7]} rc={rc}", state)
    return (f"⚠️ push refusé par le gate (rc={rc}) sur {head[:7]} — corrige puis relance : un commit le "
            f"retente, ou la porte repassée puis `echo rc=0 >> {PUSH_LOG}`")


REGEN = "tools/dev/regen_generated.py"


def start_push(root: Path) -> int:
    log = root / PUSH_LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    # The fleet master pushed → the fleet is reconciled right after (T66): a validated change
    # reaches every `managed` repo without a second gesture. Elsewhere the file is absent.
    # T247: the push's own time, as a `source: push` row — the A25 delay starts there, not at the
    # apply (which may wait on the lock) nor at the commit (which may wait days for its push).
    row = (f'printf \'{{"source": "push", "head": "%s", "at": "%s", "how": "auto"}}\\n\' '
           f'"$h" "$(date +%Y-%m-%dT%H:%M:%S%z)" >> {APPLY_HISTORY}')
    # T653: the log is overwritten by the next push; the journal (>>) keeps every verdict, apply's included.
    hist = root / PUSH_HISTORY
    # T804: the gate judges the working tree, so its derived files are rendered right before the push, here
    # and not earlier in on_stop (every checklist writer of the turn has run). A failed render pushes nothing.
    # Only the master has the module. Render-to-gate stays an open window, counted on real Stops (R214).
    cmd = (f'cd "{root}" && {{ date -Is; h=$(git rev-parse HEAD); rc=0; '
           f'[ -f {REGEN} ] && {{ python3 {REGEN} --worktree; rc=$?; }}; '
           f'[ "$rc" = 0 ] && {{ git push; rc=$?; }}; echo "rc=$rc"; '
           f'echo "rc=$rc head=$h" >> "{hist}"; }} > "{log}" 2>&1; '
           f'[ "$rc" = 0 ] && [ -f {APPLY} ] && {{ mkdir -p {Path(APPLY_HISTORY).parent}; {row}; '
           f'python3 {APPLY} apply --push >> "{log}" 2>&1; echo "apply_rc=$? head=$h" >> "{hist}"; }}')
    return subprocess.Popen(["bash", "-c", cmd], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True).pid


def _apply_tail(root: Path) -> list[dict]:
    """The rows about the apply (`source: apply`, or `deferred` with `action: apply`), newest first — the tail only."""
    try:
        with (root / APPLY_HISTORY).open("rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 256_000))
            tail = f.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []
    rows = []
    for line in reversed(tail):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and (row.get("source") == "apply"
                                      or (row.get("source") == "deferred" and row.get("action") == "apply")):
            rows.append(row)
    return rows


def deferred_at(root: Path, head: str) -> float | None:
    """T613: the time fleet_apply deferred THIS HEAD's apply (a session live in another repo), when that deferral is
    the last word on the apply — None once an apply ran, or for another HEAD."""
    rows = _apply_tail(root)
    if rows and rows[0].get("source") == "deferred" and rows[0].get("head") == head:
        return rows[0].get("t")
    return None


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
    # T782: the verdict goes to the journal too (`apply_rc=` + head, as the apply chained to a push writes it):
    # one journal, this log is only the detail. `rc=` stays in the log for the readers of the legacy trace.
    hist = root / PUSH_HISTORY
    cmd = (f'cd "{root}" && {{ date -Is; h=$(git rev-parse HEAD); python3 {APPLY} apply --push; rc=$?; '
           f'echo "apply_rc=$rc head=$h" >> "{hist}"; echo "rc=$rc"; }} > "{log}" 2>&1')
    subprocess.Popen(["bash", "-c", cmd], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def push_seen(root: Path, head: str) -> None:
    """T247: a push this hook did not make (by hand) — its time is unknown, the first Stop that sees
    HEAD at its upstream writes it: `how: vu`, a LOWER bound of the push → conformity delay."""
    path = root / APPLY_HISTORY
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"source": "push", "head": head, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                            "how": "vu"}) + "\n")


def apply_failure(root: Path) -> str | None:
    """T653/T782: « <head7> apply rc=N #k » of the last apply that failed, from the journal (`apply_rc=` rows,
    written by the apply chained to a push AND by `start_apply`). `#k` is the row's rank: a second failed retry of
    the same head is a new key, so it reaches the open row. Only a journal with no `apply_rc=` row at all falls
    back to the legacy trace of `start_apply` — a stale failing log can never mask a newer green row. Else None."""
    log, hist = root / APPLY_LOG, root / PUSH_HISTORY
    rows = (re.findall(r"^apply_rc=(\d+) head=(\w+)", hist.read_text(encoding="utf-8", errors="replace"), re.M)
            if hist.is_file() else [])
    if rows:
        return f"{rows[-1][1][:7]} apply rc={rows[-1][0]} #{len(rows)}" if rows[-1][0] != "0" else None
    if log.is_file():
        rcs = re.findall(r"^rc=(\d+)$", log.read_text(encoding="utf-8", errors="replace"), re.M)
        if rcs and rcs[-1] != "0":
            return f"fleet-apply rc={rcs[-1]}"
    return None


def maybe_apply(root: Path, state: dict) -> str | None:
    """T159: the master at its upstream, on a HEAD no apply has seen → apply, once per HEAD."""
    if not (root / APPLY).is_file() or "0" in (os.environ.get("ROADMAP_AUTOAPPLY"), os.environ.get("ROADMAP_AUTOPUSH")):
        return None
    if (failed := apply_failure(root)) and state.get("apply_failed_said") != failed:
        state["apply_failed_said"] = failed  # once per failure; the row is the lasting channel
        reopen_refusal(root, "apply-échoué", failed, state)
    if git(root, "rev-parse", "--git-dir").stdout.strip() != git(root, "rev-parse", "--git-common-dir").stdout.strip():
        return None  # a linked worktree: its HEAD is not the master's
    head = git(root, "rev-parse", "HEAD").stdout.strip()
    up = git(root, "rev-parse", "@{u}")
    if not head or up.returncode or up.stdout.strip() != head:
        return None
    if not state.get("push_pending") and state.get("push_seen_head") != head:
        state["push_seen_head"] = head  # once per HEAD; an auto push already wrote its exact row
        push_seen(root, head)
        save(root, state)
    t = deferred_at(root, head)
    if (state.get("launched_head") == head and t is not None and not state.get("push_pending")
            and time.time() - t >= DEFER_RETRY_S and state.get("deferred_retried") != t):
        state.pop("launched_head")  # T613: launched, then deferred by a session elsewhere — not « applied »: retry,
        state["deferred_retried"] = t  # once per deferral row (a relaunch that writes none is not retried forever)
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
    state, msgs = load(root), []
    if report := push_report(root, state):
        msgs.append(report)
    prune_parked(root, state)  # before the flush AND before save(): the Stop block in main reads this saved state
    written, _dropped = flush_refusals(root, state)  # T686b: before ANY read of the checklist below, and before a gate reads it
    if written:
        msgs.append(f"⚠️ {written} refus différé(s) pendant un gate, écrit(s) au tableau des tâches ouvertes")
    text = sync_anchor(path.read_text(encoding="utf-8"), prefix)  # in memory: the write comes last, after the push decision (T686b)
    if report := ci_report(root, path, state, time.time()):
        msgs.append(report)
        text = sync_anchor(path.read_text(encoding="utf-8"), prefix)  # a red CI put its task back in the index
    if state.get("session") != session:  # SessionStart missed: snapshot now, act from next turn
        state.update(session=session, start=dirty(root))
    ids, idx = all_ids(text, prefix), index_ids(text, title, prefix)
    closed = sorted((set(state.get("open", [])) - ids) | closed_this_turn(root, path, prefix, ids))
    if closed and os.environ.get("ROADMAP_AUTOCOMMIT") != "0":
        write_anchor(path, prefix)  # the commit below carries the synced anchor, as it always did
        now = dirty(root)
        files = touched(state.get("start", {}), now)
        if files:
            msg = f"{', '.join(closed)} fermée{'s' if len(closed) > 1 else ''} — commit automatique"
            r = commit_with_retry(root, files, msg)
            if r.returncode == 0:
                msgs.append(f"✅ {msg} ({len(files)} fichier(s))")
                state["start"] = {p: h for p, h in state.get("start", {}).items() if p not in files}
            else:
                git(root, "reset", "-q", "--", *files)
                full = "\n".join(x for x in (r.stderr, r.stdout) if x).strip()
                why = refusal_summary(full) or str(r.returncode)
                journal_refusal(root, f"commit-refusé {', '.join(closed)} (rc={r.returncode}, {getattr(r, 'stage', '?')})", full)
                msgs.append(f"⚠️ commit automatique refusé pour {', '.join(closed)} : {why}")
                reopen_refusal(root, "commit-refusé", f"{', '.join(closed)} : {why}")  # no gate in flight: the commit precedes the push
    text = path.read_text(encoding="utf-8")  # a refusal above may have put a row back (T653)
    ids, idx = all_ids(text, prefix), index_ids(text, title, prefix)
    launched = False
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
            args = (state.get("index"), len(idx), ahead, behind, bool(state.get("push_pending")),
                    head, state.get("refused_head"))
            waiting = False
            if decide_push(*args) and ci_local_running(root):  # T686a
                if state.get("ci_wait", 0) < CI_WAIT_MAX_STOPS:
                    waiting = True
                    state["ci_wait"] = state.get("ci_wait", 0) + 1
                    msgs.append("⏳ index à 0 : push différé, un ci-local tourne (réessayé au prochain tour)")
                elif state.get("ci_wait") == CI_WAIT_MAX_STOPS:
                    state["ci_wait"] += 1
                    msgs.append(f"⚠️ ci-local toujours en cours après {CI_WAIT_MAX_STOPS} tours : attente abandonnée, push lancé")
            if decide_push(*args, ci_running=waiting):
                state.pop("ci_wait", None)
                launched = True
                state.update(push_pending=True, push_head=head, launched_head=head, push_pid=start_push(root))
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
    if not launched and not gate_in_flight(root, state):
        write_anchor(path, prefix)  # T686b: never ahead of a push, never under a gate
    text = path.read_text(encoding="utf-8")
    ids, idx = all_ids(text, prefix), index_ids(text, title, prefix)
    state.update(open=sorted(ids), index=len(idx))
    if state.get("pending_refusals"):
        msgs.append(f"⛔ {len(state['pending_refusals'])} refus en attente d'écriture (gate en cours) : "
                    f"{refusal_names(state)} — écrit(s) au prochain tour, une fois le gate fini")
    save(root, state)
    return msgs


def refusal_names(state: dict) -> str:
    return ", ".join(f"{m} ({d})" for m, d in state.get("pending_refusals", []))


def write_anchor(path: Path, prefix: str) -> bool:
    """T34: the `reprise:` anchor rewritten on disk when stale. True when the file changed."""
    text = path.read_text(encoding="utf-8")
    if (synced := sync_anchor(text, prefix)) == text:
        return False
    path.write_text(synced, encoding="utf-8")
    return True


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
        out = {"systemMessage": " · ".join(msgs)}
        parked = load(root).get("pending_refusals")
        if parked and not payload.get("stop_hook_active"):  # T686b: a parked refusal still blocks the Stop, once per cycle
            out.update(decision="block", reason=f"Refus non écrit au tableau (gate en cours) : {refusal_names({'pending_refusals': parked})}")
        print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception:  # noqa: BLE001 — automation never blocks the end of a turn
        sys.exit(0)
