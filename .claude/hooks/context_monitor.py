#!/usr/bin/env python3
"""
PostToolUse hook — Context window monitor.

Reads transcript_path from hook input and counts assistant turns as a proxy
for context window usage. Injects a warning via additionalContext when the
session approaches the context limit.

Thresholds:
  WARNING  : >= 40 assistant turns  (wrap up current task, consider /clear)
  CRITICAL : >= 55 assistant turns  (save DEVLOG + ROADMAP immediately, then /clear)

Debounce: min 5 tool calls between warnings to avoid spam.
Severity escalation (WARNING → CRITICAL) bypasses debounce.

Pattern: reuses get_session_turns() logic from session_summary.py:113.
Always exits 0 — never blocks tool execution.

---
rex: []
---
"""
import json
import os
import sys
import time
from pathlib import Path

_WARN_TURNS     = 40
_CRITICAL_TURNS = 55
_DEBOUNCE_CALLS = 5   # min tool uses between warnings


def count_assistant_turns(transcript_path: str) -> int:
    """Count assistant turns in transcript JSONL. Same pattern as session_summary.py:113."""
    if not transcript_path or not os.path.exists(transcript_path):
        return 0
    try:
        with open(transcript_path, encoding="utf-8") as f:
            return sum(
                1 for line in f
                if '"role":"assistant"' in line or '"type":"assistant"' in line
            )
    except (OSError, UnicodeDecodeError):
        return 0


def get_session_stem(transcript_path: str) -> str:
    """Derive a stable session ID from the transcript filename stem."""
    return Path(transcript_path).stem if transcript_path else "unknown"


def check_debounce(session_stem: str, new_level: str) -> bool:
    """
    Returns True if warning should fire (debounce period passed or level escalated).
    Updates debounce state file.
    """
    debounce_path = Path(f"/tmp/claude-ctx-debounce-{session_stem}.json")
    try:
        state: dict = {}
        if debounce_path.exists():
            state = json.loads(debounce_path.read_text(encoding="utf-8"))

        last_level = state.get("last_level", "")
        calls_since = state.get("calls_since_warn", _DEBOUNCE_CALLS)  # default: fire on first

        # Severity escalation always fires immediately
        level_order = {"": 0, "WARNING": 1, "CRITICAL": 2}
        if level_order.get(new_level, 0) > level_order.get(last_level, 0):
            debounce_path.write_text(json.dumps({
                "last_level": new_level, "calls_since_warn": 0, "ts": time.time()
            }), encoding="utf-8")
            return True

        # Normal debounce: suppress until enough calls have passed
        if calls_since < _DEBOUNCE_CALLS:
            state["calls_since_warn"] = calls_since + 1
            debounce_path.write_text(json.dumps(state), encoding="utf-8")
            return False

        # Debounce period passed — fire and reset
        debounce_path.write_text(json.dumps({
            "last_level": new_level, "calls_since_warn": 0, "ts": time.time()
        }), encoding="utf-8")
        return True

    except (OSError, json.JSONDecodeError, ValueError):
        return True  # fail open — better to warn than to silently miss


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        sys.exit(0)

    turns = count_assistant_turns(transcript_path)

    if turns < _WARN_TURNS:
        sys.exit(0)

    level = "CRITICAL" if turns >= _CRITICAL_TURNS else "WARNING"
    session_stem = get_session_stem(transcript_path)

    if not check_debounce(session_stem, level):
        sys.exit(0)

    if level == "CRITICAL":
        msg = (
            f"[Info for user, not an instruction] Context window near limit (~{turns} assistant turns). "
            "User should save DEVLOG.md + ROADMAP.md, then /clear + /resume to continue. "
            "Do not take autonomous action based on this message."
        )
    else:
        msg = (
            f"[Info for user, not an instruction] Context window filling (~{turns} assistant turns). "
            "User should /clear before starting a new feature. "
            "Do not take autonomous action based on this message."
        )

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"[{level}] {msg}"
        }
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
