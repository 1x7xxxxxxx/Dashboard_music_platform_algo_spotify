"""Un magasin de credentials illisible pour TOUS n'est pas « aucun artiste connecté ».

Type: Test
Uses: importlib, unittest.mock
Depends on: airflow/dags/*.py, src/utils/credential_loader.py
Persists in: nothing

Le défaut, presque livré le 2026-09-17 et attrapé par
`tests/test_e2e_two_tenants.py::test_credential_store_failure_does_not_borrow_an_identity` :

En fermant `multitenant-dag-fleet-poisoning`, j'ai mis la lecture des credentials dans
un `try … except: continue` par locataire. Correct pour l'isolement — mais le `continue`
arrive **AVANT** le compteur de locataires configurés. Un magasin en panne pour tout le
monde donnait donc `configured == 0`, la garde « échouer si TOUS ont échoué » ne se
déclenchait pas, et **une panne totale se lisait comme « aucun artiste connecté »** :
tâche verte, zéro ligne, aucun signal. Classe `une-erreur-avalée-devient-une-absence`.

La propriété testée ici est celle-là, et pas le mécanisme : *quand la lecture des
credentials échoue pour CHAQUE locataire, la tâche LÈVE.* Elle ne dit pas quelle
exception ni par quel chemin — ce sont les DAG qui choisissent (ils relèvent l'exception
d'origine, dont le type nomme le magasin).

⚠️ Ce test n'a pas de faux jumeau utile : un DAG qui n'a AUCUN locataire actif ne doit
PAS lever, et c'est la seconde propriété ci-dessous. Sans elle, le remède évident —
« lever dès qu'on n'a rien collecté » — transformerait une flotte vide en panne.

Mutation record — 2026-09-17, quatre mutations, quatre vues ROUGES : retirer
`unreadable.append(e)` de chacun des quatre DAG → le DAG concerné cesse de lever.

---
rex: []
---
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# (module de DAG, fonction de tâche, module où `load_platform_credentials` est LU)
_COLLECTORS = [
    ("soundcloud_daily", "run_soundcloud_collector"),
    ("instagram_daily", "run_insta_collector"),
    ("youtube_daily", "collect_youtube_data"),
    ("meta_ads_api_daily", "run_meta_api_collector"),
]


def _load_dag(name: str):
    path = _ROOT / "airflow" / "dags" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_dag_{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _context() -> dict:
    dag_run = MagicMock()
    dag_run.conf = {}
    return {"dag_run": dag_run, "task_instance": MagicMock(), "run_id": "test-run"}


def test_the_task_functions_named_here_still_exist() -> None:
    """Anti-vacuité : un nom de tâche qui a changé rendrait ce test muet."""
    manquantes = []
    for dag_name, task in _COLLECTORS:
        try:
            module = _load_dag(dag_name)
        except Exception as exc:                      # noqa: BLE001
            pytest.skip(f"{dag_name} non importable ici : {type(exc).__name__}: {exc}")
        if not callable(getattr(module, task, None)):
            manquantes.append(f"{dag_name}.{task}")
    assert not manquantes, f"tâches introuvables : {manquantes}"


@pytest.mark.parametrize("dag_name,task", _COLLECTORS, ids=[d for d, _ in _COLLECTORS])
def test_a_store_unreadable_for_every_tenant_raises(dag_name: str, task: str) -> None:
    """La panne totale du magasin doit LEVER, jamais rendre une tâche verte et vide."""
    from src.utils.credential_loader import CredentialLoadError

    try:
        module = _load_dag(dag_name)
    except Exception as exc:                          # noqa: BLE001
        pytest.skip(f"{dag_name} non importable ici : {type(exc).__name__}: {exc}")

    # ⚠️ On patche le module SOURCE, pas l'attribut du module de DAG. Les tâches font
    # `from src.utils.credential_loader import …` À L'INTÉRIEUR de la fonction, donc un
    # `patch.object(module, …)` ne serait jamais vu : la ré-importation rend la vraie.
    # Mesuré le 2026-09-17 — la frontière HTTP du `conftest` a arrêté le test après
    # **12 connexions sortantes RÉELLES** vers l'API, ce qui est exactement ce qu'elle
    # existe pour attraper.
    fleet = [(11, "Tenant A"), (12, "Tenant B")]
    with patch("src.utils.credential_loader.get_active_artists", return_value=fleet), \
         patch("src.utils.credential_loader.load_platform_credentials",
               side_effect=CredentialLoadError("store down")):
        with pytest.raises(Exception) as caught:      # noqa: PT011 — le TYPE est au DAG
            getattr(module, task)(**_context())

    assert not isinstance(caught.value, AssertionError), (
        f"{dag_name}.{task} n'a pas levé sur une panne totale du magasin — "
        "une tâche verte et vide se lit comme « aucun artiste connecté »")


@pytest.mark.parametrize("dag_name,task", _COLLECTORS, ids=[d for d, _ in _COLLECTORS])
def test_an_empty_fleet_does_not_raise(dag_name: str, task: str) -> None:
    """Le faux jumeau : zéro locataire actif est un état NORMAL, pas une panne.

    Sans cette propriété, le remède évident — « lever dès qu'on n'a rien collecté » —
    ferait rougir chaque nuit un déploiement neuf.
    """
    try:
        module = _load_dag(dag_name)
    except Exception as exc:                          # noqa: BLE001
        pytest.skip(f"{dag_name} non importable ici : {type(exc).__name__}: {exc}")

    with patch("src.utils.credential_loader.get_active_artists", return_value=[]):
        try:
            getattr(module, task)(**_context())
        except Exception as exc:                      # noqa: BLE001
            pytest.fail(f"{dag_name}.{task} a levé sur une flotte VIDE : "
                        f"{type(exc).__name__}: {exc}")
