#!/usr/bin/env python3
"""
Hook Stop — Session summary: git + Docker + session length + pytest + deliverable freshness.

Runs at end of session. Silent if nothing to report. Always exits 0.

---
rex:
  - date: 2026-05-31
    issue: "_DELIVERABLES + the latest.md resume pointer referenced ROADMAP.md, which does not exist in this repo"
    fix: "Repointed both to .claude/dev-docs/roadmap/checklist.md (the single source of truth)"
    severity: warn
---
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# Noisy patterns to skip in git summary
_SKIP_PATTERNS = (
    ".pyc", ".pyo",
    "__pycache__/",
    "mlruns/",
)

# Docker containers expected when the project's stack is up.
# Empty by default — projects override in their own .claude/hooks/session_summary.py
# after bootstrap (e.g. ("api", "postgres", "redis") for a typical web app).
_EXPECTED_CONTAINERS: tuple[str, ...] = (
    "postgres_spotify_airflow",
    "airflow_scheduler",
    "airflow_webserver",
)

# Warn threshold for long sessions
_SESSION_TURNS_WARN = 20

# Deliverable files to check for freshness (relative to repo root).
# REX is no longer a freshness target — captured per-tool via frontmatter (see rex-format.md).
_DELIVERABLES = {
    "checklist.md":      ".claude/dev-docs/roadmap/checklist.md",
    "DEVLOG.md":         "DEVLOG.md",
}


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
    modified = [line for line in lines if line.startswith((" M", "M "))]
    deleted  = [line for line in lines if line.startswith((" D", "D "))]
    new      = [line for line in lines if line.startswith("?")]
    staged   = [line for line in lines if not line.startswith((" ", "?"))]

    counts = []
    if modified: counts.append(f"✏️  {len(modified)} modifié(s)")
    if new:      counts.append(f"➕ {len(new)} nouveau(x)")
    if deleted:  counts.append(f"🗑️  {len(deleted)} supprimé(s)")
    if staged:   counts.append(f"📦 {len(staged)} stagé(s)")

    header = f"\n📁 {len(lines)} fichier(s) modifiés — " + "  ".join(counts)
    detail = "\n  ".join([""] + lines[:5])
    if len(lines) > 5:
        detail += f"\n  … et {len(lines) - 5} autre(s)"
    reminder = '\n💡 Before /clear : update DEVLOG.md, check off checklist.md items, run /retro to promote pending REX drafts'
    return header + detail + reminder


# ── Docker ───────────────────────────────────────────────────────────────────

def _find_docker() -> str | None:
    """Cherche docker dans le PATH puis dans le chemin Windows classique."""
    found = shutil.which("docker")
    if found:
        return found
    win_path = "/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe"
    return win_path if os.path.exists(win_path) else None


def check_docker_health() -> list[str]:
    """Returns warnings for expected containers that are not running.

    Silent if _EXPECTED_CONTAINERS is empty (default — generic payload), if Docker
    is unreachable, or if none of the expected containers are running yet (stack
    not up — not actionable).
    """
    if not _EXPECTED_CONTAINERS:
        return []
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
        if not any(c in running for c in _EXPECTED_CONTAINERS):
            return []  # stack not up — not actionable
        warnings = [
            f"  🔴 {c} not running"
            for c in _EXPECTED_CONTAINERS
            if c not in running
        ]
        return warnings
    except (subprocess.TimeoutExpired, OSError):
        return []  # Docker unreachable → silent


# ── Session length ────────────────────────────────────────────────────────────

def get_session_turns(transcript_path: str) -> int:
    """Compte les tours assistant dans le transcript JSONL."""
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


# ── Deliverable freshness ─────────────────────────────────────────────────────

# ── Pytest ───────────────────────────────────────────────────────────────────

def run_pytest_summary(repo_root: str) -> str | None:
    """Run pytest and return a short summary line. None if tests dir not found."""
    tests_dir = os.path.join(repo_root, "src", "Application", "tests")
    app_dir   = os.path.join(repo_root, "src", "Application")
    if not os.path.isdir(tests_dir):
        return None
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", tests_dir, "--tb=no", "-q", "--no-header"],
            capture_output=True, text=True, timeout=60, cwd=app_dir,
        )
        output = (result.stdout + result.stderr).strip()
        # Truncate to avoid token overflow — keep the summary line(s)
        if len(output) > 600:
            output = "…\n" + output[-580:]
        last_line = output.splitlines()[-1] if output else ""
        if result.returncode == 0:
            return f"\n✅ Tests: {last_line}"
        else:
            msg = f"\n❌ Tests failing:\n  {last_line}"
            failures = sum(1 for line in output.splitlines() if " FAILED" in line)
            if failures >= 5:
                msg += f"\n  → {failures} failures — consider spawning build-error-resolver agent"
            return msg
    except subprocess.TimeoutExpired:
        return "\n⏱️  Tests timed out (>60s) — check for hanging fixtures"
    except (OSError, UnicodeDecodeError):
        return None


# ── Config vs DEVLOG sync check ───────────────────────────────────────────────

# Files/dirs that must be reflected in DEVLOG when modified
_CONFIG_WATCH = [
    ".claude/rules",          # rules files (domain conventions)
    "tools",                  # setup-claude-code.sh and other tooling
    "CLAUDE.md",              # root project instructions
    ".claude/hooks",          # hook scripts
    ".claude/skills",         # skill files
]


def check_config_devlog_sync(repo_root: str) -> list[str]:
    """Warn if config files are newer than DEVLOG.md — means unlogged work."""
    devlog = os.path.join(repo_root, "DEVLOG.md")
    if not os.path.exists(devlog):
        return []

    devlog_mtime = os.path.getmtime(devlog)
    newer = []

    for watch in _CONFIG_WATCH:
        full = os.path.join(repo_root, watch)
        if os.path.isfile(full):
            if os.path.getmtime(full) > devlog_mtime:
                newer.append(os.path.relpath(full, repo_root))
        elif os.path.isdir(full):
            for fname in os.listdir(full):
                fpath = os.path.join(full, fname)
                if os.path.isfile(fpath) and os.path.getmtime(fpath) > devlog_mtime:
                    newer.append(os.path.relpath(fpath, repo_root))

    if not newer:
        return []

    lines = [f"  📝 {f}" for f in sorted(newer)[:8]]
    if len(newer) > 8:
        lines.append(f"  … et {len(newer) - 8} autre(s)")
    return lines


# ── Deliverable freshness ─────────────────────────────────────────────────────

def check_deliverables_freshness() -> list[str]:
    """Warn about deliverable files that don't contain today's date."""
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    today = datetime.now().strftime("%Y-%m-%d")
    warnings = []

    for label, rel_path in _DELIVERABLES.items():
        full = os.path.join(base, rel_path)
        if not os.path.exists(full):
            warnings.append(f"  📄 {label} missing — create it")
            continue
        try:
            content = Path(full).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if today not in content:
            warnings.append(f"  📄 {label} not updated today ({today})")

    return warnings


# ── Latest snapshot (written on every Stop so /resume is always fresh) ────────

def _git_branch(repo_root: str) -> str:
    try:
        r = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=repo_root, timeout=5,
        )
        return r.stdout.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def _latest_devlog_title(repo_root: str) -> str:
    devlog = Path(repo_root) / "DEVLOG.md"
    if not devlog.exists():
        return "N/A"
    for line in reversed(devlog.read_text(encoding="utf-8", errors="ignore").splitlines()):
        if line.startswith("## "):
            return line[3:].strip()
    return "N/A"


def _extract_state_lines(lines: list[str]) -> list[str]:
    result: list[str] = []
    in_sec = False
    for line in lines:
        if line.startswith("## Current state"):
            in_sec = True
            continue
        if in_sec:
            if line.startswith("## "):
                break
            if line.strip():
                result.append(line)
            if len(result) >= 3:
                break
    return result or ["(no current state)"]


def _wip_snapshot(repo_root: str) -> str:
    wip_dir = Path(repo_root) / ".claude" / "dev-docs" / "work-in-progress"
    if not wip_dir.exists():
        return "None"
    folders = [d for d in wip_dir.iterdir() if d.is_dir() and d.name != "__pycache__"]
    if not folders:
        return "None"
    parts = []
    for folder in folders:
        ctx = folder / "context.md"
        if not ctx.exists():
            parts.append(f"**{folder.name}** — no context.md")
            continue
        lines = ctx.read_text(encoding="utf-8", errors="ignore").splitlines()
        parts.append(f"**{folder.name}**\n" + "\n".join(_extract_state_lines(lines)))
    return "\n\n".join(parts)


def write_latest_snapshot(repo_root: str, git_changes: list[str]) -> None:
    """Overwrite latest.md with current session state. Called on every Stop."""
    sessions_dir = Path(repo_root) / ".claude" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch = _git_branch(repo_root)
    git_str = "\n".join(f"  {line}" for line in git_changes[:10]) or "  (clean)"
    devlog = _latest_devlog_title(repo_root)
    wip = _wip_snapshot(repo_root)

    content = (
        f"# Session State — {timestamp}\n"
        f"*Saved by Stop hook (session_summary.py) — refreshed after each response*\n\n"
        f"## Git branch\n{branch}\n\n"
        f"## Git status\n{git_str}\n\n"
        f"## Last DEVLOG entry\n{devlog}\n\n"
        f"## Active WIP\n{wip}\n\n"
        f"## Resume instructions\n"
        f"After /clear or session restart:\n"
        f"1. Run `/resume` (reads `.claude/dev-docs/roadmap/checklist.md` — the single source of truth)\n"
        f"2. Re-run `python3 -m pytest tests/ -q` to confirm test state\n"
    )
    try:
        (sessions_dir / "latest.md").write_text(content, encoding="utf-8")
    except OSError:
        pass  # non-fatal — hook must never block the session


# ── Observations visibility ───────────────────────────────────────────────────

def _check_observations(repo_root: str) -> str | None:
    project_name = Path(repo_root).name or "default"
    obs = Path(repo_root) / ".claude" / "homunculus" / project_name / "observations.jsonl"
    if not obs.exists():
        return None
    try:
        count = sum(1 for _ in obs.open(encoding="utf-8"))
    except OSError:
        return None
    if count > 50:
        return (
            f"\n💡 {count} observations logged in observations.jsonl"
            " — run /continuous-learning to extract reusable patterns"
        )
    return None


def _check_pending_rex(repo_root: str) -> str | None:
    pending = Path(repo_root) / ".claude" / "sessions" / "pending-rex.md"
    if not pending.exists():
        return None
    try:
        text = pending.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    n_drafts = text.count("\n## ")
    if n_drafts == 0:
        return None
    return (
        f"\n📝 {n_drafts} REX draft(s) pending in .claude/sessions/pending-rex.md"
        " — run /retro (review + promote) or /rex-promote (promote only) before /clear"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    transcript_path = data.get("transcript_path", "")
    # Strip `.claude/hooks/` (two levels) to land at the repo root — previously
    # stripped only one level which produced `.claude/.claude/sessions/` artifacts.
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sections = []

    # 1. Git changes
    changes = get_git_changes()
    write_latest_snapshot(repo_root, changes)
    if changes:
        sections.append(format_git_summary(changes))

    # 2. Docker health
    docker_warnings = check_docker_health()
    if docker_warnings:
        sections.append("\n⚠️  Expected containers down:\n" + "\n".join(docker_warnings)
                        + "\n  → docker compose up -d")

    # 3. Session length
    turns = get_session_turns(transcript_path)
    if turns >= _SESSION_TURNS_WARN:
        sections.append(
            f"\n🔢 Long session ({turns} turns) — "
            "check token usage with /cost and consider /clear after this task."
        )

    # 4. Pytest hint — not auto-run (too expensive per Stop).
    # Run manually: python3 -m pytest src/Application/tests/ -q --tb=short
    py_changes = [line for line in changes if line.endswith(".py")]
    if py_changes:
        sections.append(
            f"\n🧪 {len(py_changes)} .py file(s) changed — run tests before /clear:\n"
            "  cd src/Application && python3 -m pytest tests/ -q --tb=short"
        )

    # 5. Config/DEVLOG sync check
    config_newer = check_config_devlog_sync(repo_root)
    if config_newer:
        sections.append(
            "\n⚠️  Config files modified but DEVLOG.md not updated:\n"
            + "\n".join(config_newer)
            + "\n  → Add a DEVLOG entry before /clear to avoid losing context"
        )

    # 6. Deliverable freshness
    deliverable_warnings = check_deliverables_freshness()
    if deliverable_warnings:
        sections.append(
            "\n📋 Post-session deliverables not updated:\n"
            + "\n".join(deliverable_warnings)
            + "\n  → Update checklist.md, DEVLOG.md before /clear; run /retro to promote pending REX drafts"
        )

    # 7. Observations visibility
    obs_hint = _check_observations(repo_root)
    if obs_hint:
        sections.append(obs_hint)

    # 8. Pending REX drafts
    rex_hint = _check_pending_rex(repo_root)
    if rex_hint:
        sections.append(rex_hint)

    if sections:
        print("\n" + "─" * 50)
        print("".join(sections))
        print("─" * 50)

    sys.exit(0)


if __name__ == "__main__":
    main()
