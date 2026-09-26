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


def undocumented(compose_text: str, documented: set) -> list[str]:
    """Required `${VAR}` of a compose file that `.env.example` does not document. Pure.

    ${VAR} and ${VAR:?msg} → required; ${VAR:-default} → optional (baked default).
    `:?` must count: the variables it marks are the MOST required of all, and the
    bare-`}` regex alone dropped them from this check the day they were hardened.
    """
    required = set(re.findall(r"\$\{([A-Z0-9_]+)(?:\}|:\?)", compose_text))
    required -= set(re.findall(r"\$\{([A-Z0-9_]+):-", compose_text))
    required.discard("VAR")  # placeholder de doc dans l'en-tête
    return sorted(required - documented)


def test_the_detector_sees_the_defect_it_is_written_for():
    """Non-vacuity: a `${VAR:?}` hardened the day it was added — dropped by the first
    regex — and a bare `${VAR}` are both named when undocumented; a `${VAR:-default}`
    and a documented variable are not."""
    compose = ("environment:\n"
               "  - PASSWORD=${DATABASE_PASSWORD:?set it in .env}\n"
               "  - KEY=${FERNET_KEY}\n"
               "  - PORT=${PORT:-8080}\n"
               "  - USER=${DB_USER}\n")
    assert undocumented(compose, {"DB_USER"}) == ["DATABASE_PASSWORD", "FERNET_KEY"]
    assert undocumented(compose, {"DB_USER", "DATABASE_PASSWORD", "FERNET_KEY"}) == []


def test_every_required_compose_var_is_documented_in_env_example():
    documented = set(re.findall(r"^([A-Z0-9_]+)=", ENV_EXAMPLE.read_text(), re.M))
    manquantes = {}
    for f in _COMPOSE_FILES:
        if not f.exists():
            continue
        absentes = undocumented(f.read_text(), documented)
        if absentes:
            manquantes[f.name] = absentes
    assert not manquantes, (
        "des fichiers compose référencent des ${VAR} requises non documentées dans "
        f".env.example (ajoute-les pour que le déployeur sache quoi poser) : {manquantes}"
    )


# A variable without which the stack cannot start must make compose REFUSE, not warn.
# Compose resolves an unset `${VAR}` to "" with a warning nobody reads: on 2026-09-23
# `airflow-init` died late on "Airflow Admin password not set" because
# AIRFLOW_ADMIN_* were missing from `.env` — the file compose reads (never `.env.local`).
# `${VAR:?msg}` stops `docker compose up` before any container starts, naming the fix.
_STACK_CANNOT_START_WITHOUT = {
    "DATABASE_PASSWORD",       # postgres refuses to initialise with an empty superuser password
    "AIRFLOW_ADMIN_USERNAME",  # airflow-init exits 1
    "AIRFLOW_ADMIN_PASSWORD",  # airflow-init exits 1
    "FERNET_KEY",              # every stored tenant credential becomes undecryptable
}


def test_a_variable_the_stack_cannot_start_without_is_mandatory():
    text = COMPOSE.read_text()
    faibles = sorted(v for v in _STACK_CANNOT_START_WITHOUT
                     if re.search(r"\$\{" + v + r"(\}|:-)", text))
    absentes = sorted(v for v in _STACK_CANNOT_START_WITHOUT
                      if not re.search(r"\$\{" + v + r":\?", text))
    assert not faibles and not absentes, (
        f"{COMPOSE.name} : {faibles or absentes} doivent s'écrire `${{VAR:?message}}`. "
        "Un `${VAR}` vide devient une chaîne vide avec un simple avertissement, et le "
        "conteneur meurt plus tard sur un message qui n'accuse pas `.env`.")
