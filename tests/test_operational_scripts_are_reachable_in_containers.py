"""An operational script must be reachable from where its dependencies live.

Measured 2026-08-21 on the live server: the documented production procedure
    docker exec streamlytics_dashboard python3 tools/create_canary.py …
failed with `can't open file '/app/tools/create_canary.py'`.

The split is the whole problem: `tools/` sits on the HOST, where psycopg2 is not
installed; psycopg2 lives in the CONTAINERS, where `tools/` was not mounted. So a
runbook step that reads perfectly cannot execute anywhere.

This is the same class as `probe-scoped-to-the-machine-not-the-repo`, which is why
`src/utils/central_apps.py` was moved out of `tools/` in the first place — the
lesson had been learnt for one script and not applied to its neighbours.

Error class: script-unreachable-from-its-dependencies.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / "docker-compose.example.yml"

# Scripts an operator is told to run against a deployed environment.
OPERATIONAL = [
    "tools/create_canary.py",
    "tools/artist_preflight.py",
    "tools/tenant_contamination_check.py",
]

AIRFLOW_SERVICES = ("airflow-webserver", "airflow-scheduler", "airflow-init")


@pytest.fixture(scope="module")
def compose() -> dict:
    if not COMPOSE.is_file():
        pytest.skip("docker-compose.example.yml absent")
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("rel", OPERATIONAL)
def test_the_script_exists(rel: str) -> None:
    assert (ROOT / rel).is_file(), f"{rel} is referenced as operational but missing"


@pytest.mark.parametrize("service", AIRFLOW_SERVICES)
def test_tools_is_mounted_wherever_src_is(service: str, compose: dict) -> None:
    """Anywhere the app code is mounted, the scripts that drive it must be too."""
    services = compose.get("services", {})
    if service not in services:
        pytest.skip(f"{service} not declared")
    volumes = services[service].get("volumes") or []
    mounts = [v if isinstance(v, str) else v.get("source", "") for v in volumes]

    has_src = any(m.startswith("./src:") for m in mounts)
    if not has_src:
        pytest.skip(f"{service} does not mount ./src either")

    assert any(m.startswith("./tools:") for m in mounts), (
        f"{service} mounts ./src but not ./tools. The operational scripts need "
        "psycopg2, which exists only inside the containers — so the documented "
        "production procedure cannot run anywhere. Add:\n"
        "      - ./tools:/opt/airflow/tools:ro"
    )


def test_the_mount_is_read_only(compose: dict) -> None:
    """These scripts are read from inside a container, never written to."""
    for service in AIRFLOW_SERVICES:
        volumes = compose.get("services", {}).get(service, {}).get("volumes") or []
        for v in volumes:
            if isinstance(v, str) and v.startswith("./tools:"):
                assert v.endswith(":ro"), (
                    f"{service} mounts ./tools writable. A container that can rewrite "
                    "the repo's operational scripts is a surprise nobody wants."
                )
