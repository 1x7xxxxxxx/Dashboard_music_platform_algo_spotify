#!/usr/bin/env python3
"""Stop — a beep when the roadmap reaches 0 open task, never at night.
---
rex: []
---

Type: Hook
Uses: governance.toml ([roadmap] dir, id_prefix) or streamlytics' .claude/dev-docs/roadmap/
Persists in: .claude/sessions/roadmap-empty-beep.json (the last count seen)
Triggers: powershell.exe MediaPlayer, a soft chime at rising volume (WSL), afplay (macOS), BEL otherwise

Owner's request (2026-10-16): « un bip quand la roadmap est à 0 tâche », allowed only
between 09:20 and 01:00 — « la nuit je dors et faut pas que ça me réveille ». It beeps on the
TRANSITION to 0 (n > 0 → 0), once, not at every turn of an empty roadmap. A transition reached
at night is kept pending (the count is not recorded) and beeps at the first turn after 09:20
if the roadmap is still empty. A first run records the count without beeping, so installing
the hook on an already-empty roadmap is silent. ROADMAP_BEEP=0 silences it. Never fails a turn.

T74 (2026-10-18): a message of the fleet mailbox not yet handled counts as an open task, so the
beep means « roadmap ET boîte à 0 » — the goal a session works towards.

T83 (2026-10-18): the row citing `msg:<id>` was only asked for in the session's context. A
message taken and cited by no row now blocks the end of the turn ONCE per session (`decision:
block`, never while `stop_hook_active`): the model writes the row, or a « sans suite » one.
The row is the model's to write — its id, priority and « Mesuré par » differ by repo.

T94 (2026-10-18, owner: « dès qu'on a des items on roadmap on les développe de façon automatique,
le reste va dans en attente de toi »): a row of « 📋 Tâches ouvertes » still open at the end of a
turn blocks it ONCE per row and session — the model develops it now, or moves it to « 🙋 En
attente de toi » when it needs a gesture of the owner. Rows of the waiting table never block.
ROADMAP_AUTODEV=0 silences it.

T158 (2026-10-19): « session finished » was decided on a subset of what session_closable.checks()
measures — a repo at 0 row, dirty and 1 commit ahead, ended its turn without a word. Once the
« 📋 Tâches ouvertes » table is at 0, the six proofs of session_closable (the master's, through
~/.fleet-master/tools/hud — a local tools/hud first) are read and commit, push, gate and mailbox
block, ONCE per state: commit/push keyed on HEAD (not on a count that moves every turn) and only
when seen red on TWO consecutive Stops — roadmap_autocommit runs beside this hook and commits /
launches the push on the very turn the index reaches 0; gate keyed on (HEAD, rc); mailbox on the
set of message ids. A push is never prescribed by hand (rule 5): without upstream the owner is
asked; with one the automatic push is said pending or refused. `tasks` never blocks (a running
background task is not the model's to finish) and nothing blocks while `stop_hook_active`. No
session_closable, or one that raises or exceeds CLOSABLE_S → the behaviour before T158.
ROADMAP_CLOSABLE=0 silences it.

guard_scope: both index tables of the checklist (open and waiting-on-a-human — both are open
tasks), the window, the transition, the closable blocks and their keys. NOT covered: a muted
Windows sound output.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
from datetime import datetime, time
from importlib import import_module
from importlib.util import find_spec, module_from_spec, spec_from_file_location
from pathlib import Path

# R365 (streamlytics): a hook leaves one trace line per run when the repo has _hook_trace.py; elsewhere a no-op.
sys.path.insert(0, str(Path(__file__).resolve().parent))
_trace = getattr(import_module("_hook_trace") if find_spec("_hook_trace") else None, "trace", lambda _path: None)
_trace(__file__)

QUIET_FROM, QUIET_UNTIL = time(1, 0), time(9, 20)
STATE = Path(".claude/sessions/roadmap-empty-beep.json")


def allowed(now: datetime) -> bool:
    """09:20 ≤ t, or t < 01:00 — the window crosses midnight."""
    return not (QUIET_FROM <= now.time() < QUIET_UNTIL)


def checklist(root: Path) -> tuple[Path, str]:
    rdir, prefix = ".claude/dev-docs/roadmap", "R"
    toml = root / "governance.toml"
    if toml.is_file():
        import tomllib
        cfg = tomllib.loads(toml.read_text(encoding="utf-8")).get("roadmap", {})
        rdir, prefix = cfg.get("dir", "docs/roadmap"), cfg.get("id_prefix", "R")
    return root / rdir / "checklist.md", prefix


def open_count(text: str, prefix: str = "R") -> int:
    """Distinct ids in the index rows, as roadmap.py index_ids counts them."""
    return len(set(re.findall(rf"^\|\s*({re.escape(prefix)}\d{{1,5}})\s*\|", text, re.M)))


MAILBOX = Path.home() / ".fleet-master/tools/hud/fleet_mailbox.py"


def mailbox_state(root: Path, tool: Path = MAILBOX) -> dict:
    """This repo's fleet box (T74: handled = its roadmap row closed): `pending` count as open
    tasks — the end-of-roadmap beep waits for the box too — and `untracked` lists the taken
    messages no row cites yet (T83). No tool → nothing pending."""
    if not tool.is_file():
        return {}
    try:
        r = subprocess.run([sys.executable, str(tool), "state", root.name, str(root)],
                           capture_output=True, text=True, timeout=10)
        return json.loads(r.stdout) if r.returncode == 0 else {}
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        return {}


def mailbox_pending(root: Path, tool: Path = MAILBOX) -> int:
    try:
        return int(mailbox_state(root, tool).get("pending", 0))
    except (TypeError, ValueError):
        return 0


def gate(untracked: list[str], hook: dict, asked: dict) -> tuple[str | None, dict]:
    """(block reason or None, ids asked per session). Once per message and session, never on
    a turn the gate itself prolonged — a model that answers « sans suite » is not asked again."""
    sid = str(hook.get("session_id") or "?")
    done = set(asked.get(sid, []))
    new = [i for i in untracked if i not in done]
    if not new or hook.get("stop_hook_active"):
        return None, asked
    reason = ("Boîte aux lettres : " + ", ".join(f"msg:{i}" for i in new) + " pris sans ligne de roadmap. "
              "Inscris pour CHACUN une ligne qui cite son msg:<id> (ou « sans suite : <raison> »), "
              "puis mène-la à la fermeture.")
    return reason, {sid: sorted(done | set(new))}


OPEN_TITLE = "## 📋 Tâches ouvertes"


def todo_ids(text: str, prefix: str = "R") -> list[str]:
    """The ids of the « 📋 Tâches ouvertes » table only — not those waiting on the owner."""
    i = text.find(OPEN_TITLE)
    if i < 0:
        return []
    body = text[i + len(OPEN_TITLE):]
    j = body.find("\n## ")
    body = body if j < 0 else body[:j]
    return list(dict.fromkeys(re.findall(rf"^\|\s*({re.escape(prefix)}\d{{1,5}})\s*\|", body, re.M)))


def todo_gate(ids: list[str], hook: dict, asked: dict) -> tuple[str | None, dict]:
    """(block reason or None, ids asked per session) — T94, same once-per-session rule as gate()."""
    sid = str(hook.get("session_id") or "?")
    done = set(asked.get(sid, []))
    new = [i for i in ids if i not in done]
    if not new or hook.get("stop_hook_active") or os.environ.get("ROADMAP_AUTODEV") == "0":
        return None, asked
    reason = ("Roadmap : " + ", ".join(new) + " ouverte(s) dans « 📋 Tâches ouvertes ». Développe-les "
              "maintenant, jusqu'à la fermeture (roadmap.py close) — sans attendre qu'on te le demande. "
              "Une ligne qui exige un geste du propriétaire (achat, choix, mot de passe, BIOS) passe "
              "dans « 🙋 En attente de toi » : dis-le-lui en une ligne.")
    return reason, {sid: sorted(done | set(new))}


CLOSABLE_S = 20  # the budget of session_closable.checks(): beyond, the hook behaves as before T158
BLOCKING = ("commit", "push", "gate", "mailbox")  # never `tasks`, never `roadmap` (todo_gate's)
AUTOCOMMIT_STATE = Path(".claude/sessions/roadmap-autocommit.json")
AUTOPUSH_LOG = ".claude/sessions/roadmap-autopush.log"


def _expired(_sig, _frame):
    raise TimeoutError("session_closable")


def closable(root: Path, hook: dict) -> tuple[list[tuple[str, bool, str]], object] | None:
    """(session_closable.checks(), its module) — None when absent, broken or too slow: the import
    brings the master's hud and fleet_mailbox into another repo's process, so import AND call are
    one guarded block."""
    if os.environ.get("ROADMAP_CLOSABLE") == "0":
        return None
    tool = next((d / "session_closable.py" for d in (root / "tools/hud", Path.home() / ".fleet-master/tools/hud")
                 if (d / "session_closable.py").is_file()), None)
    if tool is None:
        return None
    alarm = hasattr(signal, "SIGALRM")
    old = signal.signal(signal.SIGALRM, _expired) if alarm else None
    try:
        if alarm:
            signal.alarm(CLOSABLE_S)
        spec = spec_from_file_location("session_closable", tool)
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)
        tr = hook.get("transcript_path")
        res = [(str(n), bool(o), str(w)) for n, o, w in mod.checks(root, Path(tr) if tr else None)]
        return res, mod
    except Exception:  # noqa: BLE001 — a broken detector never blocks nor fakes a red
        return None
    finally:
        if alarm:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)


def _box_ids(root: Path) -> str:
    """The ids of this repo's box (unread and taken), for the mailbox key: a set, not a count."""
    mb = sys.modules.get("fleet_mailbox")
    box = getattr(mb, "BOX", Path.home() / ".claude/fleet-mailbox") / root.name
    return ",".join(sorted(f.stem for f in [*box.glob("*.json"), *box.glob("read/*.json")])) if box.is_dir() else ""


def closable_gate(res: list[tuple[str, bool, str]], hook: dict, root: Path, head: str, ac: dict | None,
                  memo: dict) -> tuple[str | None, dict]:
    """(block reason or None, this session's memo {seen, said}). `ac` is roadmap_autocommit's state
    (None: unreadable this turn — being written beside us — so push and gate wait a turn)."""
    seen_before, said = set(memo.get("seen", [])), set(memo.get("said", []))
    reds = {n: w for n, ok, w in res if not ok and n in BLOCKING}
    ac_ = ac or {}
    autopush = os.environ.get("ROADMAP_AUTOPUSH") != "0"
    pending = bool(ac_.get("push_pending"))
    refused = ac_.get("refused_head")
    msgs, seen = [], set()

    def ask(key: str, text: str, twice: bool) -> None:
        seen.add(key)
        if key not in said and (not twice or key in seen_before):
            said.add(key)
            msgs.append(text)

    if "commit" in reds:
        ask(f"commit@{head}", f"Commit : {reds['commit']} alors que l'index est à 0 — `git status`, puis "
            "commite ce qui est à toi (ou ignore-le dans .gitignore) ; ce que tu n'as pas écrit, dis-le.", True)
    if "push" in reds and ac is not None and not pending:
        if reds["push"] == "pas d'amont":
            ask(f"push@{head}", "Push : pas d'amont — demande au propriétaire avant tout `push -u` (règle 5) ; "
                "ne le fais pas toi-même.", True)
        elif not autopush:
            ask(f"push@{head}", f"Push : {reds['push']} et push automatique coupé (ROADMAP_AUTOPUSH=0) — "
                "dis-le au propriétaire (règle 5), ne pousse pas à la main.", True)
        elif ac_.get("behind_head") == head:
            ask(f"push@{head}", f"Push : {reds['push']} mais la branche est en retard sur l'amont — "
                "`git pull --rebase`, le push automatique repart au tour suivant.", True)
        # else: roadmap_autocommit pushes this HEAD (index at 0), or the gate below says its refusal
    if "gate" in reds and ac is not None and not pending and not (autopush and refused and refused != head):
        rc = reds["gate"].rsplit("rc=", 1)[-1]
        ask(f"gate@{head}@{rc}", f"Porte : {reds['gate']} — push automatique refusé, voir `tail {AUTOPUSH_LOG}`. "
            "Corrige, puis relance la porte (le master : `python3 tools/dev/blast_radius.py --run`) et "
            f"`echo rc=0 >> {AUTOPUSH_LOG}` : le push automatique repart (et repasse la porte).", False)
    if "mailbox" in reds:
        ask(f"mailbox@{_box_ids(root)}", f"Boîte aux lettres : {reds['mailbox']} — "
            f"`python3 ~/.fleet-master/tools/hud/fleet_mailbox.py state {root.name} {root}`, puis une ligne "
            "de roadmap par message (msg:<id>).", False)
    if not msgs or hook.get("stop_hook_active"):  # a prolonged turn records what it saw, says nothing
        return None, {"seen": sorted(seen), "said": sorted(memo.get("said", []))}
    memo = {"seen": sorted(seen), "said": sorted(said)}
    return "Séance pas encore fermable (session_closable) : " + " · ".join(msgs), memo


def decide(last: int | None, now_open: int, now: datetime) -> tuple[bool, int | None]:
    """(beep?, count to record). None recorded = keep the previous one (pending)."""
    if last is None:
        return False, now_open
    if now_open == 0 and last > 0:
        return (True, 0) if allowed(now) else (False, None)
    return False, now_open


# Owner's request (2026-10-16, second): « plus doux et moins agressif … volume croissant ». A soft
# Windows chime played three times at rising volume, instead of three square-wave console beeps.
CHIME = r"C:\Windows\Media\Windows Notify Calendar.wav"
VOLUMES = (0.12, 0.25, 0.45)
PS_FADE_IN = (
    "Add-Type -AssemblyName PresentationCore;"
    "if (-not (Test-Path '{chime}')) {{ [console]::beep(660,120); exit }};"
    "foreach ($v in @({volumes})) {{"
    " $p = New-Object System.Windows.Media.MediaPlayer; $p.Open([uri]'{chime}'); $p.Volume = $v;"
    " $p.Play(); Start-Sleep -Milliseconds 1700; $p.Close() }}"
)


def beep() -> None:
    kw = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "start_new_session": True}
    if shutil.which("powershell.exe"):
        script = PS_FADE_IN.format(chime=CHIME, volumes=",".join(str(v) for v in VOLUMES))
        subprocess.Popen(["powershell.exe", "-NoProfile", "-STA", "-Command", script], **kw)
    elif platform.system() == "Darwin" and shutil.which("afplay"):
        for v in VOLUMES:  # afplay -v: same rising volume, sequential
            subprocess.run(["afplay", "-v", str(v), "/System/Library/Sounds/Glass.aiff"], **kw)
    else:
        with open("/dev/tty", "w") as tty:
            tty.write("\a")


def main() -> int:
    try:
        hook = json.loads(sys.stdin.read() or "{}") if not sys.stdin.isatty() else {}
    except ValueError:
        hook = {}
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    root = Path(out.stdout.strip()) if out.returncode == 0 else Path.cwd()
    path, prefix = checklist(root)
    if not path.is_file():
        return 0
    state = root / STATE
    try:
        saved = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    box = mailbox_state(root)
    reason, asked = gate(list(box.get("untracked") or []), hook, saved.get("asked") or {})
    text = path.read_text(encoding="utf-8")
    now_open = open_count(text, prefix) + int(box.get("pending") or 0)
    ids = todo_ids(text, prefix)
    if not reason:
        reason, todo = todo_gate(ids, hook, saved.get("todo") or {})
    else:
        todo = saved.get("todo") or {}
    memos = saved.get("closable") or {}
    sid = str(hook.get("session_id") or "?")
    if not reason and not ids and (got := closable(root, hook)):
        head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
                              text=True).stdout.strip()
        try:
            ac = json.loads((root / AUTOCOMMIT_STATE).read_text(encoding="utf-8"))
        except FileNotFoundError:
            ac = {}
        except (OSError, ValueError):
            ac = None
        reason, memo = closable_gate(got[0], hook, root, head, ac, memos.get(sid) or {})
        memos = {sid: memo}
    ring, record = decide(saved.get("last_open"), now_open, datetime.now())
    record = saved.get("last_open") if record is None else record
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"last_open": record, "asked": asked, "todo": todo, "closable": memos}), encoding="utf-8")
    if ring and os.environ.get("ROADMAP_BEEP") != "0":
        beep()
    if reason:
        print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 — a notification never blocks the end of a turn
        sys.exit(0)
