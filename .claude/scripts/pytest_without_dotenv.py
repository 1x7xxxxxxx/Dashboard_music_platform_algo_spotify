"""Plugin pytest : neutralise les fichiers `.env` du poste, comme un runner CI.

Type: Utility
Uses: pytest, src.utils.env_files
Triggers: signature de la classe `guard-reads-the-box-not-its-subject`
Depends on: src/utils/env_files.py (ENV_FILES)
Persists in: nothing

Pourquoi
--------
Un garde dont le verdict vient du `.env` du poste est vert là où il a été écrit et
ne peut pas passer là où il tourne. Le 2026-09-05, `test_the_sandbox_default_address
_is_deliverable` a rougi la CI pour cette seule raison : il lisait l'adresse de
l'opérateur sur la machine au lieu de la poser. Sur ce poste il passait ; sur un
runner, qui n'a pas de `.env`, il ne pouvait pas.

Le reproduire en cachant `.env` serait destructeur. Ce plugin remplace
`load_project_env` par une fonction qui ne charge rien, avant toute collecte : un
test qui pose ce qu'il lit reste vert, un test qui le lisait sur la machine rougit.

C'est la FONCTION qui est neutralisée, pas la constante `ENV_FILES`. Vider la
constante a d'abord paru équivalent et ne l'était pas :
`test_the_standalone_mailer_honours_the_same_env_precedence` compare `ENV_FILES` au
tuple du mailer autonome — le vider faisait rougir un test dont c'est précisément le
sujet. Un détecteur ne mute pas ce qu'il mesure.

Portée : le chargeur de l'application. `tools/notify_schema_drift.py` porte
délibérément le sien (un import cassé ne doit pas pouvoir taire l'alerte de dérive) et
n'est donc pas neutralisé ici.

Usage :

    PYTHONPATH=.claude/scripts python3 -m pytest <cible> -q -p pytest_without_dotenv

---
rex: []
---
"""
from __future__ import annotations


def pytest_configure(config) -> None:      # noqa: ARG001
    import src.utils.env_files as env_files

    def _load_nothing(override: bool = False) -> list[str]:   # noqa: ARG001
        return []

    env_files.load_project_env = _load_nothing
