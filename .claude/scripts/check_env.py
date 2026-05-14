#!/usr/bin/env python3
"""
Generic environment prerequisite check.

Verifies: Python ≥ 3.10, .env presence, .venv + pyyaml (for validate_rex.py),
Docker daemon (optional). Project owners extend this script with stack-specific
checks (DB ports, required tooling, ...).

Run manually: python3 .claude/scripts/check_env.py
Or via:       /check-env

---
rex: []
---
"""
import os
import shutil
import subprocess
import sys


# ── Repo root ─────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))               # .claude/scripts/
CLAUDE_DIR  = os.path.dirname(SCRIPT_DIR)                              # .claude/
REPO_ROOT   = os.path.dirname(CLAUDE_DIR)                              # project root
ENV_FILE    = os.path.join(REPO_ROOT, ".env")
ENV_TEMPLATE = os.path.join(REPO_ROOT, ".env.template")


def ok(msg: str)   -> None: print(f"  ✅  {msg}")
def warn(msg: str) -> None: print(f"  ⚠️   {msg}")
def fail(msg: str) -> None: print(f"  ❌  {msg}")


# ── Checks ────────────────────────────────────────────────────────────────────

def check_python() -> bool:
    v = sys.version_info
    if v >= (3, 10):
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
        return True
    fail(f"Python {v.major}.{v.minor} < 3.10 required")
    return False


def check_venv_pyyaml() -> bool:
    venv_python = os.path.join(REPO_ROOT, ".venv", "bin", "python3")
    if not os.path.exists(venv_python):
        warn(".venv missing — run: python3 -m venv .venv && source .venv/bin/activate && pip install pyyaml")
        return False
    r = subprocess.run([venv_python, "-c", "import yaml"], capture_output=True, text=True)
    if r.returncode == 0:
        ok(".venv present + pyyaml installed")
        return True
    warn(".venv present but pyyaml missing — run: source .venv/bin/activate && pip install pyyaml")
    return False


def check_env_file() -> bool:
    if not os.path.exists(ENV_FILE):
        if os.path.exists(ENV_TEMPLATE):
            warn(".env missing — copy .env.template to .env and fill in values")
        else:
            warn(".env missing (and no .env.template either — projects typically need both)")
        return False
    ok(".env present")
    return True


def check_docker() -> bool:
    docker = shutil.which("docker")
    if not docker:
        win_path = "/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe"
        if os.path.exists(win_path):
            docker = win_path
    if not docker:
        warn("docker not found — install Docker Desktop (skip if your project is non-containerized)")
        return True  # non-blocking — many projects don't use Docker
    try:
        r = subprocess.run([docker, "info"], capture_output=True, timeout=4)
        if r.returncode == 0:
            ok("Docker daemon reachable")
            return True
        warn("Docker found but daemon not responding — start Docker Desktop")
        return True  # non-blocking
    except (subprocess.TimeoutExpired, OSError):
        warn("Docker unreachable — start Docker Desktop")
        return True  # non-blocking


def check_git() -> bool:
    if shutil.which("git"):
        ok("git available")
        return True
    fail("git not found — install via your package manager")
    return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n🔍 Environment Check")
    print("─" * 50)

    results = {
        "Python ≥ 3.10":     check_python(),
        ".venv + pyyaml":     check_venv_pyyaml(),
        ".env file":          check_env_file(),
        "git":                check_git(),
        "Docker (optional)":  check_docker(),
    }

    print("─" * 50)
    passed = sum(results.values())
    total  = len(results)
    if passed == total:
        print(f"✅  All {total} checks passed — environment ready\n")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"⚠️   {passed}/{total} checks passed. Fix: {', '.join(failed)}\n")

    print("ℹ️  Add project-specific checks in .claude/scripts/check_env.py "
          "(DB ports, required CLIs, secret backup acknowledgement, etc.)")


if __name__ == "__main__":
    main()
