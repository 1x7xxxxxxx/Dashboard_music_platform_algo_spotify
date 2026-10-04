"""R357 — the on-demand container rule, judged on `docker inspect` records.

Type: Test
Uses: tools/dev/idle_containers.py
Depends on: nothing live — synthetic inspect records
Persists in: nothing

What must hold:
1. the shared test database may run;
2. a `--rm -i` container (an MCP stdio server of the session) may run;
3. anything else running at rest is a violation;
4. `restart: always` is a violation even on a stopped container;
5. `unless-stopped` on a stopped container is not.

Mutation record (2026-10-04): seen red with the `session_scoped` exemption widened to
`AutoRemove` alone, with the `always` branch removed, and with ALWAYS_ON ignored.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "dev"))

from idle_containers import violations  # noqa: E402


def _c(name: str, running: bool, policy: str = "no", rm: bool = False,
       stdin: bool = False) -> dict:
    return {"Name": f"/{name}", "State": {"Running": running},
            "HostConfig": {"RestartPolicy": {"Name": policy}, "AutoRemove": rm},
            "Config": {"OpenStdin": stdin}}


def test_the_test_database_and_session_servers_may_run() -> None:
    assert violations([_c("postgres_spotify_airflow", True, "unless-stopped"),
                       _c("gifted_germain", True, rm=True, stdin=True)]) == []


def test_anything_else_running_at_rest_is_a_violation() -> None:
    got = violations([_c("n8n-ollama", True), _c("batch", True, rm=True)])
    assert [v.split(" :")[0] for v in got] == ["n8n-ollama", "batch"]


def test_restart_always_is_a_violation_even_stopped() -> None:
    assert violations([_c("hermes", False, "always")])
    assert violations([_c("hermes", False, "unless-stopped")]) == []
