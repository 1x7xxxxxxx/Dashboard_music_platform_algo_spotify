"""Un service dont d'autres dépendent revient avec l'hôte, ou rien ne repart.

Type: Test
Uses: pytest, yaml
Depends on: docker-compose.yml, docker-compose.example.yml
Persists in: nothing

Pourquoi ce garde existe
------------------------
Le 2026-09-12, WSL a redémarré. Treize conteneurs sont remontés seuls. UN seul est
resté à terre : `postgres_spotify_airflow`, la base du projet — `RestartPolicy: no`,
la seule ligne `restart:` absente de `docker-compose.yml`. Ses trois dépendants
(`airflow-init`, `airflow-webserver`, `airflow-scheduler`) portaient tous
`unless-stopped` : ils sont revenus, et ont tapé pendant des minutes contre une base
morte. Le symptôme visible n'était donc PAS « la base est tombée » mais « Airflow
tourne et ne voit rien », ce qui envoie chercher au mauvais endroit.

`docker-compose.example.yml`, le fichier de production, portait la ligne depuis
toujours. C'est une dérive entre les deux composes que `test_compose_parity.py` ne
regardait pas : il compare les montages et les services, pas les politiques de
reprise.

Classe d'erreur : `a-dependency-that-does-not-come-back`.

L'invariant tient en une phrase : **si un service B déclare `depends_on: A` avec une
condition d'exécution (`service_healthy` / `service_started`), alors A doit déclarer
une politique de redémarrage au moins aussi durable que celle de B.** Un lanceur
à un coup (`service_completed_successfully`) est exempté — il a VOCATION à sortir.

Mutations vues rouges avant écriture (2026-09-12) :
  - retirer `restart: unless-stopped` de `postgres` dans docker-compose.yml
    → test_a_depended_on_service_declares_a_restart_policy ÉCHOUE en nommant
      `docker-compose.yml :: postgres`, ses 3 dépendants et la ligne à ajouter ;
  - poser `restart: "no"` sur `postgres` → même test ÉCHOUE (politique plus faible
    que celle des dépendants) ;
  - retirer la ligne de `docker-compose.example.yml` → ÉCHOUE sur l'autre fichier,
    donc la parité est gardée dans les deux sens.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[1]
_COMPOSES = ("docker-compose.yml", "docker-compose.example.yml")

# Du plus faible au plus durable. Un service dont on dépend ne peut pas être
# moins durable que celui qui en dépend.
_DURABILITY = {"no": 0, "on-failure": 1, "always": 2, "unless-stopped": 2}

# Une condition qui n'attend PAS la fin du service : le dépendant a besoin qu'il
# TOURNE, donc qu'il revienne.
_RUNNING_CONDITIONS = {"service_healthy", "service_started"}


def _load(name: str) -> dict:
    path = _ROOT / name
    if not path.exists():
        pytest.skip(f"{name} absent")
    # utf-8-sig : docker-compose.yml porte un BOM.
    return yaml.safe_load(io.open(path, encoding="utf-8-sig")) or {}


def _depends(service: dict) -> dict[str, str]:
    """Rend {nom_du_service_requis: condition}, les deux formes de `depends_on`."""
    raw = service.get("depends_on") or {}
    if isinstance(raw, list):  # forme courte : pas de condition ⇒ service_started
        return {name: "service_started" for name in raw}
    return {
        name: (spec or {}).get("condition", "service_started")
        for name, spec in raw.items()
    }


def _policy(service: dict) -> str | None:
    value = service.get("restart")
    return None if value is None else str(value).strip().strip('"').strip("'")


@pytest.mark.parametrize("compose", _COMPOSES)
def test_a_depended_on_service_declares_a_restart_policy(compose: str) -> None:
    """Un service requis TOURNANT par un autre remonte au moins aussi durablement."""
    services = (_load(compose).get("services") or {})
    faults: list[str] = []

    for dependent_name, dependent in services.items():
        if not isinstance(dependent, dict):
            continue
        dependent_policy = _policy(dependent) or "no"
        for required_name, condition in _depends(dependent).items():
            if condition not in _RUNNING_CONDITIONS:
                continue  # lanceur à un coup : il DOIT sortir
            required = services.get(required_name)
            if not isinstance(required, dict):
                continue
            required_policy = _policy(required)
            if required_policy is None:
                faults.append(
                    f"{compose} :: `{required_name}` ne déclare AUCUNE politique de "
                    f"redémarrage alors que `{dependent_name}` en dépend "
                    f"({condition}) avec `restart: {dependent_policy}`. "
                    f"Au prochain redémarrage de l'hôte, {dependent_name} revient et "
                    f"{required_name} non. Ajouter `restart: unless-stopped` au "
                    f"service `{required_name}`."
                )
                continue
            if _DURABILITY.get(required_policy, 0) < _DURABILITY.get(dependent_policy, 0):
                faults.append(
                    f"{compose} :: `{required_name}` porte `restart: "
                    f"{required_policy}`, plus faible que `{dependent_name}` "
                    f"(`{dependent_policy}`) qui en dépend ({condition}). "
                    f"Porter `{required_name}` à `{dependent_policy}`."
                )

    assert not faults, "\n".join(faults)


def test_the_two_composes_agree_on_restart_policies() -> None:
    """La politique d'un service est la même dans le compose local et l'exemple."""
    local = (_load("docker-compose.yml").get("services") or {})
    example = (_load("docker-compose.example.yml").get("services") or {})

    divergences = [
        f"`{name}` : docker-compose.yml dit `{_policy(local[name])}`, "
        f"docker-compose.example.yml dit `{_policy(example[name])}`"
        for name in sorted(set(local) & set(example))
        if isinstance(local[name], dict)
        and isinstance(example[name], dict)
        and _policy(local[name]) != _policy(example[name])
    ]

    assert not divergences, (
        "Les deux composes divergent sur la reprise après redémarrage de l'hôte — "
        "c'est exactement la forme du défaut du 2026-09-12 :\n"
        + "\n".join(divergences)
    )


def test_the_project_database_is_covered() -> None:
    """Non-vacuité : le service qui a produit la classe est bien dans la population."""
    services = (_load("docker-compose.yml").get("services") or {})
    assert "postgres" in services, "le service `postgres` a disparu du compose local"
    dependents = [
        name
        for name, svc in services.items()
        if isinstance(svc, dict)
        and _depends(svc).get("postgres") in _RUNNING_CONDITIONS
    ]
    assert dependents, (
        "aucun service ne dépend de `postgres` en condition d'exécution : le premier "
        "test ne garde plus rien. Si les dépendances ont changé, revoir ce garde."
    )
