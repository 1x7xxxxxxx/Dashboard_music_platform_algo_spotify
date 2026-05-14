#!/usr/bin/env python3
"""
Hook PreToolUse — Guard against destructive Bash commands.

Intercepts Bash tool calls before execution.
- BLOCKING (exit 2): truly irreversible operations that should never run silently
- ADVISORY (exit 0): risky operations that print a warning but are allowed through

Always exits 0 for non-Bash tools and safe commands.

Generic patterns only — projects extend this list with their own destructive
commands (admin endpoints, named volumes that hold critical state, mass-update
SQL on a key table, etc.) by appending to _BLOCK_PATTERNS / _WARN_PATTERNS.

---
rex: []
---
"""
import json
import sys


# ── Patterns ──────────────────────────────────────────────────────────────────

# Blocking: exit 2 — Claude must explain and get explicit confirmation
_BLOCK_PATTERNS: list[tuple[str, str]] = [
    ("git push --force",        "Force push overwrites remote history — use 'git push' instead"),
    ("git push -f ",            "Force push overwrites remote history — use 'git push' instead"),
    ("git reset --hard",        "Hard reset discards all uncommitted changes permanently"),
    ("git checkout -- .",       "Discards all uncommitted changes in working directory"),
    ("git restore .",           "Discards all uncommitted changes in working directory"),
    ("git clean -f",            "Permanently deletes untracked files"),
    ("git commit --no-verify",  "Skipping pre-commit hooks bypasses secret scanning"),
    ("git commit -n ",          "Skipping pre-commit hooks bypasses secret scanning"),
    ("docker system prune",     "Removes ALL unused Docker data including named volumes"),
    ("rm -rf /",                "Recursive delete from root — catastrophic"),
    ("DROP TABLE",              "Irreversible SQL table deletion"),
    ("DROP DATABASE",           "Irreversible database deletion"),
    ("DROP SCHEMA",             "Irreversible SQL schema deletion (CASCADE loses every dependent object)"),
    ("dropdb ",                 "Drops an entire database — irreversible"),
    ("mongo --eval 'db.dropDatabase()'", "Drops an entire MongoDB database — irreversible"),
    ("redis-cli FLUSHALL",      "Wipes every Redis key across every database"),
    ("redis-cli FLUSHDB",       "Wipes every key in the current Redis database"),
]

# Advisory: exit 0 — prints warning but allows through
_WARN_PATTERNS: list[tuple[str, str]] = [
    ("rm -rf",                  "Recursive delete — verify path before proceeding"),
    ("DELETE FROM",             "SQL delete — ensure WHERE clause is present and targeted"),
    ("UPDATE ",                 "SQL update — verify WHERE clause is present (mass update otherwise)"),
    ("git stash drop",          "Permanently discards stashed changes"),
    ("docker volume rm",        "Removes a Docker volume — data may be lost"),
    ("docker compose down -v",  "Removes named volumes — every persistent state in this stack is lost"),
    ("truncate",                "Truncates file content — verify target path"),
    ("pkill",                   "Kills processes — verify target process name"),
    ("docker compose pull",     "Pulling a `:latest`-tagged image silently — verify version pin"),
]


# ── Detection ─────────────────────────────────────────────────────────────────

def check_command(cmd: str) -> tuple[str, str] | None:
    """
    Returns (level, message) if the command matches a dangerous pattern.
    level is 'block' or 'warn'. Returns None if safe.
    """
    cmd_lower = cmd.lower()
    for pattern, message in _BLOCK_PATTERNS:
        if pattern.lower() in cmd_lower:
            return ("block", message)
    for pattern, message in _WARN_PATTERNS:
        if pattern.lower() in cmd_lower:
            return ("warn", message)
    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if data.get("tool_name") != "Bash":
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    result = check_command(command)
    if result is None:
        sys.exit(0)

    level, message = result

    if level == "block":
        print(
            f"🚫 BLOCKED — Destructive command detected:\n"
            f"   Command : {command[:120]}\n"
            f"   Reason  : {message}\n"
            f"   Action  : Explain the intent and request explicit user confirmation before retrying."
        )
        sys.exit(2)
    else:
        print(
            f"⚠️  WARNING — Risky command:\n"
            f"   Command : {command[:120]}\n"
            f"   Reason  : {message}\n"
            f"   Proceeding — verify this is intentional."
        )
        sys.exit(0)


if __name__ == "__main__":
    main()
