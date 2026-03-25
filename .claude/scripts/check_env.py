#!/usr/bin/env python3
"""
Type: Utility
Purpose: Verify local development environment prerequisites.
Checks: Python version, ruff, pytest, config.yaml, Docker containers.
Usage: python3 .claude/scripts/check_env.py
"""
import os
import shutil
import subprocess
import sys


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "✅" if ok else "❌"
    line = f"  {status}  {label}"
    if detail:
        line += f"  ({detail})"
    print(line)
    return ok


def run(cmd: list[str], timeout: int = 5) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


def main() -> int:
    print("\n── Environment check ──────────────────────────")
    failures = 0

    # Python version
    version = sys.version_info
    ok = version >= (3, 10)
    if not check("Python ≥ 3.10", ok, f"{version.major}.{version.minor}.{version.micro}"):
        failures += 1

    # ruff
    ok = shutil.which("ruff") is not None
    if not check("ruff installed", ok, "pip install ruff" if not ok else ""):
        failures += 1

    # pytest
    ok_run, out = run(["python3", "-m", "pytest", "--version"])
    if not check("pytest installed", ok_run, out.split("\n")[0] if ok_run else "pip install pytest"):
        failures += 1

    # config.yaml
    config_path = "config/config.yaml"
    ok = os.path.isfile(config_path)
    if not check("config/config.yaml exists", ok, "copy from config/config.example.yaml" if not ok else ""):
        failures += 1

    # .env or .env.local
    ok = os.path.isfile(".env") or os.path.isfile(".env.local")
    if not check(".env / .env.local exists", ok, "copy from .env.example" if not ok else ""):
        failures += 1

    # Docker (optional — don't fail if absent)
    docker = shutil.which("docker") or "/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe"
    docker_ok = os.path.exists(docker) if not shutil.which("docker") else True
    check("docker accessible", docker_ok, "optional — needed for Airflow")

    if docker_ok:
        ok_run, out = run([docker, "ps", "--format", "{{.Names}}"], timeout=4)
        if ok_run:
            for container in ("postgres_spotify_airflow", "airflow_scheduler", "airflow_webserver"):
                running = container in out
                check(f"  {container}", running, "docker-compose up -d" if not running else "")

    print("──────────────────────────────────────────────")
    if failures == 0:
        print("  All prerequisites met.\n")
    else:
        print(f"  {failures} prerequisite(s) missing. Fix the items above before running.\n")

    return failures


if __name__ == "__main__":
    sys.exit(main())
