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

guard_scope: both index tables of the checklist (open and waiting-on-a-human — both are open
tasks), the window, the transition. NOT covered: a muted Windows sound output.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, time
from importlib import import_module
from importlib.util import find_spec
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
    if not reason:
        reason, todo = todo_gate(todo_ids(text, prefix), hook, saved.get("todo") or {})
    else:
        todo = saved.get("todo") or {}
    ring, record = decide(saved.get("last_open"), now_open, datetime.now())
    record = saved.get("last_open") if record is None else record
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"last_open": record, "asked": asked, "todo": todo}), encoding="utf-8")
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
