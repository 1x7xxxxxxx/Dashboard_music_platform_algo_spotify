"""Guard: the canonical compose template stays internally consistent.

Type: Utility
Error class `prod-compose-drift`. The prod docker-compose.yml is untracked + hand-derived,
so it silently drifted (the Benken incident). We can't diff the untracked prod file in CI,
but we CAN keep the tracked template honest: every required `${VAR}` it references must be
documented in `.env.example`, and all expected services must be present — so a new service /
env var can't be added to compose without being documented.
"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / "docker-compose.example.yml"
ENV_EXAMPLE = ROOT / ".env.example"

EXPECTED_SERVICES = {
    "postgres", "airflow-init", "airflow-webserver", "airflow-scheduler", "dashboard", "api",
}


def test_all_expected_services_present():
    services = set(yaml.safe_load(COMPOSE.read_text())["services"])
    missing = EXPECTED_SERVICES - services
    assert not missing, f"docker-compose.example.yml is missing service(s): {sorted(missing)}"


def test_every_required_compose_var_is_documented_in_env_example():
    text = COMPOSE.read_text()
    # ${VAR}  → required; ${VAR:-default} → optional (has a baked default)
    required = set(re.findall(r"\$\{([A-Z0-9_]+)\}", text))
    optional = set(re.findall(r"\$\{([A-Z0-9_]+):-", text))
    required -= optional
    required.discard("VAR")  # `${VAR}` appears only as a doc placeholder in the header comment
    documented = set(re.findall(r"^([A-Z0-9_]+)=", ENV_EXAMPLE.read_text(), re.M))
    missing = sorted(required - documented)
    assert not missing, (
        "docker-compose.example.yml references required ${VAR}(s) not documented in "
        f".env.example (add them so a deployer knows to set them): {missing}"
    )
