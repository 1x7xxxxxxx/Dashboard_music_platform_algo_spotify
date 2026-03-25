#!/usr/bin/env python3
"""
Hook: Stop — Session summary: git changes, Docker health, session length, test results.

Runs after every Claude response. Silent if nothing to report.
Always exits 0 — never blocking.
"""
import json
import os
import re
import shutil
import subprocess
import sys


# Patterns too noisy to be useful in the git summary
_SKIP_PATTERNS = (
    ".pyc", ".pyo",
    "__pycache__/",
    "machine_learning/mlruns/",
)

# Expected Airflow containers in a dev session
_AIRFLOW_CONTAINERS = (
    "postgres_spotify_airflow",
    "airflow_scheduler",
    "airflow_webserver",
)

# Conversation turn count threshold before warning on token consumption
_SESSION_TURNS_WARN = 20


# ── Git ──────────────────────────────────────────────────────────────────────

def get_git_changes() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []
    return [
        line for line in result.stdout.strip().splitlines()
        if not any(pat in line for pat in _SKIP_PATTERNS)
    ]


def format_git_summary(lines: list[str]) -> str:
    modified = [l for l in lines if l.startswith((" M", "M "))]
    deleted  = [l for l in lines if l.startswith((" D", "D "))]
    new      = [l for l in lines if l.startswith("?")]
    staged   = [l for l in lines if not l.startswith((" ", "?"))]

    counts = []
    if modified: counts.append(f"✏️  {len(modified)} modified")
    if new:      counts.append(f"➕ {len(new)} new")
    if deleted:  counts.append(f"🗑️  {len(deleted)} deleted")
    if staged:   counts.append(f"📦 {len(staged)} staged")

    header = f"\n📁 {len(lines)} file(s) — " + "  ".join(counts)
    detail = "\n  ".join([""] + lines[:5])
    if len(lines) > 5:
        detail += f"\n  … +{len(lines) - 5} more"
    return header + detail


# ── Docker ───────────────────────────────────────────────────────────────────

def _find_docker() -> str | None:
    """Locate docker binary: PATH first, then Windows path for WSL2."""
    found = shutil.which("docker")
    if found:
        return found
    win_path = "/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe"
    return win_path if os.path.exists(win_path) else None


def check_docker_health() -> list[str]:
    """Return warnings for any expected Airflow container not running."""
    docker = _find_docker()
    if not docker:
        return []

    try:
        result = subprocess.run(
            [docker, "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=4,
        )
        if result.returncode != 0:
            return []

        running = result.stdout
        return [
            f"  🔴 {c} not running"
            for c in _AIRFLOW_CONTAINERS
            if c not in running
        ]
    except Exception:
        return []  # Docker unreachable → silent


# ── Session length ────────────────────────────────────────────────────────────

def get_session_turns(transcript_path: str) -> int:
    """Count assistant turns in the JSONL transcript."""
    if not transcript_path or not os.path.exists(transcript_path):
        return 0
    try:
        with open(transcript_path, encoding="utf-8") as f:
            return sum(
                1 for line in f
                if '"role":"assistant"' in line or '"type":"assistant"' in line
            )
    except Exception:
        return 0


# ── Pytest ────────────────────────────────────────────────────────────────────

def run_pytest() -> tuple[int, int, str]:
    """
    Run pytest in quiet mode. Returns (passed, failed, truncated_output).
    Timeout: 60 seconds. Returns (0, 0, "") on any error.
    """
    try:
        result = subprocess.run(
            ["python3", "-m", "pytest", "tests/", "--tb=no", "-q", "--no-header"],
            capture_output=True, text=True, timeout=60,
        )
        output = (result.stdout + result.stderr).strip()
        passed = int(m.group(1)) if (m := re.search(r"(\d+) passed", output)) else 0
        failed = int(m.group(1)) if (m := re.search(r"(\d+) failed", output)) else 0
        return passed, failed, output[-600:]  # truncate to last 600 chars
    except Exception:
        return 0, 0, ""


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    transcript_path = data.get("transcript_path", "")
    sections = []

    # 1. Git changes
    changes = get_git_changes()
    if changes:
        sections.append(format_git_summary(changes))

    # 2. Docker health
    docker_warnings = check_docker_health()
    if docker_warnings:
        sections.append(
            "\n⚠️  Airflow containers down:\n" + "\n".join(docker_warnings)
            + "\n  → docker-compose up -d"
        )

    # 3. Session length warning
    turns = get_session_turns(transcript_path)
    if turns >= _SESSION_TURNS_WARN:
        sections.append(
            f"\n🔢 Long session ({turns} turns) — "
            "check token usage with /cost and consider /clear after this task."
        )

    # 4. Unit test summary — only on explicit /run-tests, not after every response
    # (removed auto-pytest to reduce token overhead)

    if sections:
        print("\n" + "─" * 50)
        print("".join(sections))
        print("─" * 50)

    sys.exit(0)


if __name__ == "__main__":
    main()
