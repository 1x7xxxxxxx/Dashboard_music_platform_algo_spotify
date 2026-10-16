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
    if os.environ.get("ROADMAP_BEEP") == "0":
        return 0
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    root = Path(out.stdout.strip()) if out.returncode == 0 else Path.cwd()
    path, prefix = checklist(root)
    if not path.is_file():
        return 0
    state = root / STATE
    try:
        last = json.loads(state.read_text(encoding="utf-8")).get("last_open")
    except (OSError, ValueError):
        last = None
    ring, record = decide(last, open_count(path.read_text(encoding="utf-8"), prefix), datetime.now())
    if record is not None:
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({"last_open": record}), encoding="utf-8")
    if ring:
        beep()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 — a notification never blocks the end of a turn
        sys.exit(0)
