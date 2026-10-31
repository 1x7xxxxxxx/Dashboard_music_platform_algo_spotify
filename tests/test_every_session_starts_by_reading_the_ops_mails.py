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


def test_a_missing_recap_night_is_said_at_session_start() -> None:
    """The recap cannot report its own failure to send; the journal can. Two days without a
    logged recap is said; the day after a logged one is not."""
    text = "| 2026-09-26 13:15 | 📋 Récap de la nuit — nuit calme | test | x | — |\n"
    assert "No « 📋 Récap de la nuit » logged for 3 days" in hook.mail_banner(text, "2026-09-29")
    assert "⚠️" not in hook.mail_banner(text, "2026-09-27")


def test_the_hook_is_registered_and_prints_the_banner(tmp_path) -> None:
    settings = json.loads((_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    commands = [h["command"] for e in settings["hooks"]["SessionStart"] for h in e["hooks"]]
    assert any("session_start.py" in c for c in commands)
    # R363: run in a throwaway root — with cwd=_ROOT the hook overwrote the real session
    # marker (`.session-start-ts`) and imported the cron logs into the real defect log.
    journal = tmp_path / ".claude" / "dev-docs" / "ops-mail-journal.md"
    journal.parent.mkdir(parents=True)
    journal.write_text("| 2026-10-04 | a |\n", encoding="utf-8")
    out = subprocess.run([sys.executable, str(_HOOK)], cwd=tmp_path, capture_output=True,
                         text=True, timeout=30, stdin=subprocess.DEVNULL).stdout
    assert "from:noreply@streamlytics.fr" in out
    assert (tmp_path / ".claude" / "sessions" / ".session-start-ts").exists()


# ── R684 — the owner paused the ops mails (R572): a missing recap is no longer a fault ──
_nr_spec = importlib.util.spec_from_file_location("night_run_mails", _ROOT / "tools/dev/night_run.py")
night_run = importlib.util.module_from_spec(_nr_spec)
_nr_spec.loader.exec_module(night_run)

_RECAP = "| 2026-10-14 06:30 | 📋 Récap de la nuit — nuit calme | test | x | — |\n"


def _pause_file(root: Path, paused: bool) -> Path:
    path = root / "src" / "utils" / "ops_mail_pause.py"
    path.parent.mkdir(parents=True)
    path.write_text(f"OPS_MAIL_PAUSED = {paused}\n\ndef paused_reason():\n"
                    "    return 'paused (R572)' if OPS_MAIL_PAUSED else None\n", encoding="utf-8")
    return path


def test_a_paused_recap_is_not_called_dead_but_its_workflow_is_still_named() -> None:
    banner = hook.mail_banner(_RECAP, "2026-10-31", paused="paused (R572)")
    assert "⚠️" not in banner and "the recap itself stopped" not in banner
    assert "R572" in banner and "gh run list --workflow nightly-recap.yml" in banner
    assert "from:noreply@streamlytics.fr" in banner, "the pause does not stop artist mails"


def test_the_real_pause_flag_is_read_and_a_missing_one_keeps_the_alarm(tmp_path) -> None:
    # Read from the FILE: the imported module's flag may be patched by the suite's fixtures.
    import ast
    tree = ast.parse((_ROOT / "src/utils/ops_mail_pause.py").read_text(encoding="utf-8"))
    on = next(n.value.value for n in tree.body if isinstance(n, ast.Assign)
              and any(getattr(t, "id", None) == "OPS_MAIL_PAUSED" for t in n.targets))
    for load in (hook.ops_mail_paused, night_run.ops_mail_paused):
        assert (load(_ROOT) is not None) == on, load.__module__
        assert load(tmp_path) is None, "no flag file ⇒ not paused ⇒ the alarm stays"
    assert "the recap itself stopped" in hook.mail_banner(
        _RECAP, "2026-10-31", paused=hook.ops_mail_paused(tmp_path))


def test_both_loaders_agree_on_a_paused_and_an_active_flag(tmp_path) -> None:
    """Parity: the hook cannot import tools/dev, so the loader exists twice."""
    for paused, root in ((True, tmp_path / "on"), (False, tmp_path / "off")):
        _pause_file(root, paused)
        got = {hook.ops_mail_paused(root), night_run.ops_mail_paused(root)}
        assert got == ({"paused (R572)"} if paused else {None})


def test_night_status_still_asks_for_a_sort_and_says_the_pause() -> None:
    assert night_run.mail_line(0, "x") is None
    active = night_run.mail_line(11, None)
    paused = night_run.mail_line(11, "paused (R572)")
    assert "vieux de 11 j" in active and "R572" not in active
    assert paused.startswith(active) and "pas de récap attendu" in paused
    assert "journal absent" in night_run.mail_line(None, None)
