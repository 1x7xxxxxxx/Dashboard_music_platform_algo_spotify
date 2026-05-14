#!/usr/bin/env python3
"""
PreToolUse hook — Secret scanner on git commit.

Intercepts 'git commit' Bash calls and scans staged .py files for:
- Hardcoded credentials (SMTP passwords, OPC UA endpoints with creds, API keys)
- Debug artifacts (print(), import pdb, breakpoint())
- Commit message format (must follow feat/fix/docs/test/refactor/chore: prefix)

Blocks (exit 2) on secrets found.
Warns (exit 0 with message) on debug artifacts.
Always exits 0 for non-commit commands.

---
rex:
  - date: 2026-04-24
    issue: "pre_commit_scan manquait de pattern PG_PASSWORD/POSTGRES_PASSWORD hardcodés depuis bascule PG-only"
    fix: "Ajouté 2 regex PG_PASSWORD= et POSTGRES_PASSWORD= dans SECRET_PATTERNS; INFLUX_TOKEN conservé défensif"
    severity: warn
---
"""

import json
import os
import re
import subprocess
import sys


# ── Secret patterns (block) ───────────────────────────────────────────────────

SECRET_PATTERNS: list[tuple[str, str]] = [
    (r'password\s*=\s*["\'][^"\']+["\']',   "Hardcoded password"),
    (r'SMTP_PASSWORD\s*=\s*["\'][^"\']+',   "Hardcoded SMTP password"),
    (r'secret[_\s]*key\s*=\s*["\'][^"\']+', "Hardcoded secret key"),
    (r'opc\.tcp://[^:]+:[^@]+@',            "OPC UA URL with embedded credentials"),
    (r'api[_\s]*key\s*=\s*["\'][a-zA-Z0-9_\-]{16,}', "Hardcoded API key"),
    (r'Bearer\s+[a-zA-Z0-9_\-\.]{20,}',    "Hardcoded Bearer token"),
    (r'INFLUX_TOKEN\s*=\s*["\'][^"\']+',    "Hardcoded InfluxDB token"),
    (r'PG_PASSWORD\s*=\s*["\'][^"\']+',     "Hardcoded PostgreSQL password"),
    (r'POSTGRES_PASSWORD\s*=\s*["\'][^"\']+', "Hardcoded PostgreSQL password"),
]

# ── Debug artifact patterns (warn) ────────────────────────────────────────────

DEBUG_PATTERNS: list[tuple[str, str]] = [
    (r'^\s*print\(',          "print() in production code — use logging"),
    (r'import\s+pdb',         "import pdb — debugger import"),
    (r'pdb\.set_trace\(',     "pdb.set_trace() — debugger breakpoint"),
    (r'breakpoint\(\)',       "breakpoint() — Python 3.7+ debugger"),
    (r'^\s*import\s+ipdb',    "import ipdb — debugger import"),
]

# ── Commit message prefixes (conventional commits) ────────────────────────────

VALID_PREFIXES = ("feat:", "fix:", "docs:", "test:", "refactor:", "chore:",
                  "perf:", "ci:", "build:", "style:", "revert:")


def get_staged_py_files() -> list[str]:
    """Return list of staged .py files (excluding deleted files)."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True, text=True, timeout=10
        )
        return [f for f in result.stdout.splitlines() if f.endswith(".py")]
    except (OSError, subprocess.TimeoutExpired):
        return []


def get_file_staged_content(filepath: str) -> str:
    """Get the staged (index) content of a file."""
    try:
        result = subprocess.run(
            ["git", "show", f":{filepath}"],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def get_commit_message_from_command(command: str) -> str | None:
    """Extract -m message from git commit command."""
    match = re.search(r'-m\s+["\']([^"\']+)["\']', command)
    if match:
        return match.group(1)
    return None


def scan_file(filepath: str, content: str) -> tuple[list[str], list[str]]:
    """Returns (secret_findings, debug_findings) for a file."""
    secrets, debugs = [], []
    for i, line in enumerate(content.splitlines(), 1):
        # Skip comment lines and env var reads (os.getenv is safe)
        stripped = line.strip()
        if stripped.startswith("#") or "os.getenv" in line or "os.environ" in line:
            continue
        for pattern, label in SECRET_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                secrets.append(f"  {filepath}:{i} — {label}\n    → {stripped[:80]}")
        for pattern, label in DEBUG_PATTERNS:
            if re.search(pattern, line):
                debugs.append(f"  {filepath}:{i} — {label}\n    → {stripped[:80]}")
    return secrets, debugs


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    if data.get("tool_name") != "Bash":
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")
    if not command or "git commit" not in command:
        sys.exit(0)

    # Skip if already using --no-verify (guard_destructive.py handles that)
    if "--no-verify" in command:
        sys.exit(0)

    staged_files = get_staged_py_files()
    if not staged_files:
        sys.exit(0)

    all_secrets: list[str] = []
    all_debugs: list[str] = []

    for filepath in staged_files:
        # Skip test files for debug artifact check (print in tests is ok)
        content = get_file_staged_content(filepath)
        if not content:
            continue
        is_test = "tests/" in filepath or filepath.startswith("test_")
        secrets, debugs = scan_file(filepath, content)
        all_secrets.extend(secrets)
        if not is_test:
            all_debugs.extend(debugs)

    # Check commit message format
    msg_warnings: list[str] = []
    commit_msg = get_commit_message_from_command(command)
    if commit_msg and not any(commit_msg.startswith(p) for p in VALID_PREFIXES):
        msg_warnings.append(
            f"  Commit message does not follow conventional commits format.\n"
            f"  Got: \"{commit_msg}\"\n"
            f"  Expected prefix: {', '.join(VALID_PREFIXES[:6])}..."
        )

    # ── Block on secrets ──────────────────────────────────────────────────────
    if all_secrets:
        print(
            "🚫 BLOCKED — Hardcoded secrets detected in staged files:\n"
            + "\n".join(all_secrets)
            + "\n\nFix: Move secrets to environment variables (.env file).\n"
            "  Example: password = os.getenv('SMTP_PASSWORD')\n"
            "  Ensure .env is in .gitignore."
        )
        sys.exit(2)

    # ── Warn on debug artifacts ───────────────────────────────────────────────
    if all_debugs or msg_warnings:
        parts = []
        if all_debugs:
            parts.append(
                "⚠️  WARNING — Debug artifacts in staged files:\n"
                + "\n".join(all_debugs)
                + "\n  Consider replacing print() with logging.getLogger(__name__)."
            )
        if msg_warnings:
            parts.append("⚠️  WARNING — Commit message format:\n" + "\n".join(msg_warnings))
        print("\n\n".join(parts))
        # Advisory only — allow commit through
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
