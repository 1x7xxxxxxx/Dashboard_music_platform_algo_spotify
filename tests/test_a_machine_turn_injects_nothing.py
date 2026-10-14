"""R562 — a background-task notification injects no playbook; a human turn still does.

Type: Test
Uses: .claude/hooks/inject_context.py (run as Claude Code runs it: JSON on stdin)
Depends on: the repo's own .claude/workflows/bug-resolution.md keywords
Persists in: nothing (no session_id ⇒ the hook logs nothing, R363)

Found 2026-10-14: each subagent completion reached UserPromptSubmit as a "prompt", and
its report — keyword-dense by nature — pulled db-schema and architecture-change into
the context (2 × 12 KB) in a session about neither.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "inject_context.py"

# Keyword-dense on purpose: without the filter this text injects bug-resolution.
_BUGGY = ("bug régression traceback test rouge silent failure corruption — "
          "le test est rouge, traceback dans le collecteur")
_NOTIFICATION = (
    "<task-notification>\n<task-id>a1</task-id>\n<status>completed</status>\n"
    f"<result>{_BUGGY}</result>\n</task-notification>"
)
_SYSTEM = f"[SYSTEM NOTIFICATION - NOT USER INPUT]\nThis is an automated event.\n{_BUGGY}"


def _run(prompt: str) -> str:
    out = subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"prompt": prompt}),
                         capture_output=True, text=True, timeout=30, check=True)
    return out.stdout


def test_a_human_bug_prompt_still_injects_the_bug_playbook() -> None:
    assert "bug" in _run(_BUGGY).lower(), "the positive control is dead: nothing injected"


def test_a_task_notification_injects_nothing() -> None:
    assert _run(_NOTIFICATION) == ""


def test_a_system_notification_injects_nothing() -> None:
    assert _run(_SYSTEM) == ""


def test_a_human_prompt_that_quotes_a_marker_late_still_injects() -> None:
    # The marker is only a machine turn at the HEAD; a human pasting one deep in a
    # message about a bug is still a human turn.
    assert _run(_BUGGY + " " * 500 + "<task-notification>") != ""
