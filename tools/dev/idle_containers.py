#!/usr/bin/env python3
"""Containers on demand — which containers run, or will come back, while nothing uses them.

Type: Utility
Uses: `docker inspect` on every container of this machine
Triggers: `make night-status`-style manual runs; REQ-HARN (dev-resources) in requirements.yaml
Persists in: nothing — prints, exits 1 on a violation, 0 when Docker is absent (said aloud)

R357 (2026-10-04). The on-demand decision (three VS Code disconnects, WSL capped at 10 Go)
was applied with `docker update --restart=no`, at runtime: nothing kept it. A container may
run at rest only when it is
  * the shared test database (`ALWAYS_ON`), or
  * session-scoped: `--rm -i`, i.e. an MCP stdio server that dies with its client.
And no container may carry `restart: always` — it comes back at boot, stopped or not.
`unless-stopped` on a STOPPED container is fine: Docker leaves it down.
Not seen: a compose file that still declares `unless-stopped` — `make up` brings that back.
"""
from __future__ import annotations

import json
import subprocess
import sys

ALWAYS_ON = frozenset({"postgres_spotify_airflow"})


def violations(containers: list[dict]) -> list[str]:
    """Pure: `docker inspect` records → one sentence per violation."""
    out = []
    for c in containers:
        name = c.get("Name", "?").lstrip("/")
        host = c.get("HostConfig") or {}
        policy = (host.get("RestartPolicy") or {}).get("Name") or "no"
        running = (c.get("State") or {}).get("Running", False)
        session_scoped = host.get("AutoRemove") and (c.get("Config") or {}).get("OpenStdin")
        if policy == "always":
            out.append(f"{name} : restart=always — il revient au démarrage "
                       f"(docker update --restart=no {name})")
        elif running and name not in ALWAYS_ON and not session_scoped:
            out.append(f"{name} : allumé au repos (docker stop {name})")
    return out


def inspect_all() -> list[dict] | None:
    """Every container's inspect record, or None when Docker is not reachable."""
    try:
        ids = subprocess.run(["docker", "ps", "-aq"], capture_output=True, text=True,
                             timeout=30, check=True).stdout.split()
        if not ids:
            return []
        raw = subprocess.run(["docker", "inspect", *ids], capture_output=True, text=True,
                             timeout=60, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return json.loads(raw)


def main() -> int:
    containers = inspect_all()
    if containers is None:
        print("⏭  conteneurs : Docker injoignable — rien à juger")
        return 0
    bad = violations(containers)
    for line in bad:
        print(f"🔴 {line}")
    if not bad:
        print(f"✅ conteneurs : {len(containers)} connus, seuls "
              f"{', '.join(sorted(ALWAYS_ON))} et les serveurs de séance tournent")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
