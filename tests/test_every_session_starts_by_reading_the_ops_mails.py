"""Every session opens with the instruction to read and sort the streaMLytics mails — only those.

Type: Sub
Uses: .claude/hooks/session_start.py (mail_banner, main), .claude/settings.json
Depends on: nothing
Persists in: nothing

The owner asked (2026-09-26) that the automated mails be read and sorted at the start of
EACH session: he reads none of them, and some signals exist only there. A memory note does
not fire by itself; the SessionStart hook does. It prints the Gmail query restricted to
`from:noreply@streamlytics.fr`, dated from the journal's newest row.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_HOOK = _ROOT / ".claude" / "hooks" / "session_start.py"
_spec = importlib.util.spec_from_file_location("session_start_hook", _HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """The query is restricted to the streaMLytics sender and starts at the newest row."""
    text = "| 2026-09-20 | a |\n| 2026-09-26 12:38 | b |\n"
    banner = hook.mail_banner(text)
    assert "from:noreply@streamlytics.fr after:2026/09/26" in banner
    assert "ONLY those" in banner and "Never open" in banner
    assert "after:" not in hook.mail_banner("no rows\n")


def test_the_hook_is_registered_and_prints_the_banner(tmp_path) -> None:
    settings = json.loads((_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    commands = [h["command"] for e in settings["hooks"]["SessionStart"] for h in e["hooks"]]
    assert any("session_start.py" in c for c in commands)
    out = subprocess.run([sys.executable, str(_HOOK)], cwd=_ROOT, capture_output=True,
                         text=True, timeout=30).stdout
    assert "from:noreply@streamlytics.fr" in out
