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


# TOUS les fichiers compose versionnés, pas seulement le principal. Mesuré le
# 2026-09-18 : la production fait tourner 8 conteneurs, et `docker-compose.example.yml`
# n'en déclare que 5 — Grafana, Prometheus et node_exporter vivent dans
# `deploy/docker-compose.observability.yml` depuis ADR-026 (2026-09-16), et la réplique
# dans `deploy/docker-compose.replica.yml`. Les deux étaient hors de portée de ce garde :
# une `${VAR}` requise non documentée y serait passée sans un mot.
_COMPOSE_FILES = [
    COMPOSE,
    ROOT / "deploy" / "docker-compose.observability.yml",
    ROOT / "deploy" / "docker-compose.replica.yml",
]


def test_the_compose_inventory_is_not_empty():
    """Anti-vacuité : deux fichiers introuvables rendraient le test suivant vert à vide."""
    # TOUS, pas « au moins deux ». Les trois sont versionnés : un seuil tolérant
    # laisse disparaître un fichier, donc RÉTRÉCIT la portée du test suivant sans
    # qu'aucune assertion ne bouge. Retirer un fichier de ce parc est une décision,
    # et elle s'écrit dans `_COMPOSE_FILES`.
    absents = [str(f.relative_to(ROOT)) for f in _COMPOSE_FILES if not f.exists()]
    assert not absents, (
        f"{absents} déclaré(s) ici mais introuvable(s). Le test suivant ne les "
        "inspecterait plus, sans rougir : sa portée aurait rétréci en silence. "
        "Si le fichier a disparu pour de bon, retire-le de `_COMPOSE_FILES` — "
        "c'est une décision, pas un effet de bord.")


def test_every_required_compose_var_is_documented_in_env_example():
    documented = set(re.findall(r"^([A-Z0-9_]+)=", ENV_EXAMPLE.read_text(), re.M))
    manquantes = {}
    for f in _COMPOSE_FILES:
        if not f.exists():
            continue
        text = f.read_text()
        # ${VAR}  → required; ${VAR:-default} → optional (has a baked default)
        required = set(re.findall(r"\$\{([A-Z0-9_]+)\}", text))
        optional = set(re.findall(r"\$\{([A-Z0-9_]+):-", text))
        required -= optional
        required.discard("VAR")  # placeholder de doc dans l'en-tête
        absentes = sorted(required - documented)
        if absentes:
            manquantes[f.name] = absentes
    assert not manquantes, (
        "des fichiers compose référencent des ${VAR} requises non documentées dans "
        f".env.example (ajoute-les pour que le déployeur sache quoi poser) : {manquantes}"
    )
