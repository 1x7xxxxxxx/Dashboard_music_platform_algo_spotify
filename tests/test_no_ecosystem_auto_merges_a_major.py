"""Aucun écosystème Dependabot ne propose une majeure sans revue.

Classe `automation-gap-between-two-ecosystems`.

`.github/dependabot.yml` portait « Manual review for majors — high blast radius »
sur l'écosystème **pip**… et pas sur **docker**. Mesuré le 2026-08-24 : c'est
exactement par là que la PR #100 est passée — `apache/airflow` 2.8.1 → 3.3.0, qui
ressemble au correctif de sécurité attendu et qui aurait fait échouer l'import des
**16** DAGs (`schedule_interval` et `provide_context`, supprimés en 3.x), donc arrêté
toute la collecte.

Une majeure d'image de base est le rayon de souffle le plus large du fichier : elle
change le runtime SOUS l'application, et aucun test du dépôt ne s'exécute dedans
avant le déploiement. C'était le seul écosystème sans garde-fou.

Le garde ne demande pas « docker a-t-il la clause ? » mais « **un** écosystème
en est-il dépourvu ? » — sinon il faudrait le modifier à chaque ajout, et c'est
précisément l'oubli qu'il existe pour empêcher.
"""
import pathlib

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = ROOT / "dependabot.yml"
if not CONFIG.exists():
    CONFIG = ROOT / ".github" / "dependabot.yml"


def _updates() -> list:
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return data.get("updates", [])


def test_the_config_exists_and_declares_ecosystems():
    assert CONFIG.exists(), f"dependabot config introuvable ({CONFIG})"
    assert len(_updates()) >= 3, (
        "moins de trois écosystèmes déclarés — le fichier a été amputé, et un "
        "écosystème absent n'est pas un écosystème gardé."
    )


def _ignores_majors(update: dict) -> bool:
    for rule in update.get("ignore", []):
        if "version-update:semver-major" in rule.get("update-types", []):
            return True
    return False


@pytest.mark.parametrize("index", range(len(_updates())),
                         ids=[u.get("package-ecosystem", "?") for u in _updates()])
def test_every_ecosystem_defers_majors_to_a_human(index: int):
    update = _updates()[index]
    eco = update.get("package-ecosystem", "?")
    assert _ignores_majors(update), (
        f"l'écosystème « {eco} » laisse Dependabot proposer une MAJEURE "
        "automatiquement. Ajouter la clause présente sur les autres :\n"
        "    ignore:\n"
        '      - dependency-name: "*"\n'
        '        update-types: ["version-update:semver-major"]\n'
        "Une majeure change le runtime sous l'application ; c'est une décision "
        "humaine, pas une mise à jour."
    )
