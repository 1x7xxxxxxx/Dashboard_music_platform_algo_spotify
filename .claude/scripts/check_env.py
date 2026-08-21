#!/usr/bin/env python3
"""
MSDR environment prerequisite check.

Verifies: Python version, ruff, pytest, .env, Docker, PostgreSQL port, host UTC sync, container TZ=UTC, test suite.
Run manually: python3 .claude/scripts/check_env.py
Or via:      /check-env

---
rex:
  - date: 2026-04-24
    issue: "check_env.py REPO_ROOT calculé 1 niveau trop haut ; ❌ silencieux sur .env/requirements.txt/tests ; PG port non vérifié"
    fix: "REPO_ROOT corrigé dirname x2; regex pytest summary remplace count vestigial; ajouté check_postgres_port(); docstring alignée"
    severity: warn
---
"""
import os
import shutil
import subprocess
import sys
# `Path` was used at l.106 without being imported: /check-env crashed with a
# NameError the moment it reached the project-files check. Ruff (F821) had it,
# but this directory is outside CI's lint scope (`ruff check src/ tests/`).
from pathlib import Path


# ── Repo root ─────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))               # .claude/scripts/
CLAUDE_DIR  = os.path.dirname(SCRIPT_DIR)                              # .claude/
REPO_ROOT   = os.path.dirname(CLAUDE_DIR)                              # project root
# The application root differs per repo: this payload was cut from one where the
# code lives in `src/Application`. Detect it instead of asserting it — a check that
# reports "tests/ not found at src/Application/tests" in a repo whose tests are at
# `tests/` is not a check, it is noise that trains the reader to skip the report.
def _detect_app_dir() -> str:
    for candidate in (os.path.join(REPO_ROOT, "src", "Application"), REPO_ROOT):
        if os.path.isdir(os.path.join(candidate, "tests")):
            return candidate
    return REPO_ROOT


APP_DIR     = _detect_app_dir()


def ok(msg: str)   -> None: print(f"  ✅  {msg}")
def warn(msg: str) -> None: print(f"  ⚠️   {msg}")
def fail(msg: str) -> None: print(f"  ❌  {msg}")


# ── Checks ────────────────────────────────────────────────────────────────────

def check_python() -> bool:
    v = sys.version_info
    if v >= (3, 10):
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
        return True
    fail(f"Python {v.major}.{v.minor} < 3.10 required — upgrade or use pyenv")
    return False


def check_tool(name: str, install_hint: str) -> bool:
    if shutil.which(name):
        ok(f"{name} available")
        return True
    fail(f"{name} not found — {install_hint}")
    return False


def check_env_file() -> bool:
    candidates = [
        os.path.join(REPO_ROOT, ".env"),
        os.path.join(APP_DIR, ".env"),
    ]
    for p in candidates:
        if os.path.exists(p):
            ok(f".env found at {os.path.relpath(p, REPO_ROOT)}")
            return True
    warn(".env not found — copy .env.example and fill in values")
    return False


def check_requirements() -> bool:
    req = os.path.join(APP_DIR, "requirements.txt")
    if os.path.exists(req):
        ok("requirements.txt present")
        return True
    fail(f"requirements.txt missing at {os.path.relpath(req, REPO_ROOT)}")
    return False


def check_docker() -> bool:
    docker = shutil.which("docker")
    if not docker:
        win_path = "/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe"
        if os.path.exists(win_path):
            docker = win_path
    if not docker:
        warn("docker not found — Docker Desktop may not be running")
        return False
    try:
        r = subprocess.run([docker, "ps"], capture_output=True, timeout=4)
        if r.returncode == 0:
            ok("Docker daemon reachable")
            return True
        warn("Docker found but daemon not responding — start Docker Desktop")
        return False
    except Exception:
        warn("Docker unreachable — start Docker Desktop")
        return False


# Services this repo actually declares. A probe for a service the project does not
# use reports a real socket failure about an imaginary dependency: the reader
# learns to ignore a WARN line, which is how a check stops being a check. The
# QuestDB probe shipped unconditionally and came from the repo this payload was
# cut from — every other deployment got a permanent warning for a database it
# never had.
def _declares(*needles: str) -> bool:
    for name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml",
                 "pyproject.toml", "requirements.txt", ".env.example"):
        f = Path(name)
        if not f.is_file():
            continue
        try:
            blob = f.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        if any(n in blob for n in needles):
            return True
    return False


def check_questdb_port() -> bool:
    import socket
    if not _declares("questdb"):
        return True          # non declare : rien a verifier, et ce n'est pas un defaut
    try:
        with socket.create_connection(("localhost", 9000), timeout=2):
            ok("QuestDB port 9000 reachable")
            return True
    except OSError:
        warn("QuestDB port 9000 not reachable — run: docker compose --profile questdb up -d")
        return False


def _declared_pg_port() -> int:
    """The port THIS repo publishes Postgres on, read from compose (default 5432).

    Hardcoding 5432 warned about an unreachable database on every repo that maps
    another port — this one publishes 5433. Same reasoning as the QuestDB probe
    above: check what the project declares, not what the template assumed.
    """
    import re
    for name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml"):
        f = Path(name)
        if not f.is_file():
            continue
        try:
            blob = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = re.search(r'"?(\d{4,5}):5432"?', blob)
        if m:
            return int(m.group(1))
    return 5432


def check_postgres_port() -> bool:
    import socket
    port = _declared_pg_port()
    try:
        with socket.create_connection(("localhost", port), timeout=2):
            ok(f"PostgreSQL port {port} reachable")
            return True
    except OSError:
        warn(f"PostgreSQL port {port} not reachable — run: docker compose up -d postgres")
        return False


def check_timezone() -> bool:
    """Verify system clock is UTC-synchronized (brick sync-phase-0-clock-hygiene)."""
    timedatectl = shutil.which("timedatectl")
    if not timedatectl:
        warn("timedatectl not found — UTC sync check skipped (macOS/Windows host)")
        return True
    try:
        r = subprocess.run([timedatectl, "status"], capture_output=True, text=True, timeout=4)
        if r.returncode != 0:
            warn("timedatectl status failed — cannot verify NTP sync")
            return False
        out = r.stdout
        synced = "System clock synchronized: yes" in out
        utc_zone = "Time zone: UTC" in out or "(UTC, +0000)" in out
        if synced and utc_zone:
            ok("System clock UTC-synchronized (timedatectl)")
            return True
        msg = []
        if not synced:
            msg.append("NTP not synced")
        if not utc_zone:
            msg.append("host TZ not UTC")
        warn(f"timedatectl: {', '.join(msg)} — on IPC run: sudo timedatectl set-timezone UTC + install chrony")
        return False
    except subprocess.TimeoutExpired:
        warn("timedatectl timed out (>4s)")
        return False


def check_docker_tz_utc() -> bool:
    """Verify running compose services expose TZ=UTC (brick sync-phase-0-clock-hygiene)."""
    docker = shutil.which("docker")
    if not docker:
        win_path = "/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe"
        if os.path.exists(win_path):
            docker = win_path
    if not docker:
        warn("docker not found — TZ=UTC container check skipped")
        return True
    try:
        r = subprocess.run([docker, "ps", "--format", "{{.Names}}"], capture_output=True, text=True, timeout=4)
        if r.returncode != 0 or not r.stdout.strip():
            warn("no running containers — TZ=UTC check skipped (run: docker compose up)")
            return True
        bad = []
        for name in r.stdout.strip().splitlines():
            if not name:
                continue
            env = subprocess.run([docker, "exec", name, "env"], capture_output=True, text=True, timeout=3)
            if env.returncode != 0:
                continue
            if "TZ=UTC" not in env.stdout:
                bad.append(name)
        if bad:
            warn(f"{len(bad)} container(s) without TZ=UTC: {', '.join(bad)} — add `- TZ=UTC` to their environment block")
            return False
        ok("All running containers expose TZ=UTC")
        return True
    except subprocess.TimeoutExpired:
        warn("docker exec timed out — TZ=UTC check partial")
        return False


def check_tests() -> bool:
    tests_dir = os.path.join(APP_DIR, "tests")
    if not os.path.isdir(tests_dir):
        fail(f"tests/ directory not found at {os.path.relpath(tests_dir, REPO_ROOT)}")
        return False
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", tests_dir, "--collect-only", "-q", "--no-header"],
            capture_output=True, text=True, timeout=30, cwd=APP_DIR,
        )
        # pytest -q --collect-only prints "N tests collected" on the last non-empty line
        import re
        m = re.search(r"(\d+)\s+tests?\s+collected", r.stdout)
        count = int(m.group(1)) if m else 0
        if r.returncode == 0:
            ok(f"Test suite collectable — {count} tests found")
            return True
        fail(f"pytest collection error:\n    {r.stderr.strip()[:200]}")
        return False
    except subprocess.TimeoutExpired:
        warn("pytest collection timed out (>30s)")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n🔍 MSDR Environment Check")
    print("─" * 40)

    results = {
        "Python ≥ 3.10":    check_python(),
        "ruff":              check_tool("ruff", "pip install ruff"),
        "pytest":            check_tool("pytest", "pip install pytest"),
        ".env file":         check_env_file(),
        "requirements.txt":  check_requirements(),
        "Docker":            check_docker(),
        f"PostgreSQL :{_declared_pg_port()}": check_postgres_port(),
        **({"QuestDB :9000": check_questdb_port()} if _declares("questdb") else {}),
        "Host UTC sync":     check_timezone(),
        "Container TZ=UTC":  check_docker_tz_utc(),
        "Test suite":        check_tests(),
    }

    print("─" * 40)
    passed = sum(results.values())
    total  = len(results)
    if passed == total:
        print(f"✅  All {total} checks passed — environment ready\n")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"⚠️   {passed}/{total} checks passed. Fix: {', '.join(failed)}\n")


if __name__ == "__main__":
    main()
