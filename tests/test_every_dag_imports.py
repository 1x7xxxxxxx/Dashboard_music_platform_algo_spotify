"""Les 16 DAGs s'importent hors du conteneur. Ce n'était pas vrai avant le 2026-08-24.

Ce dépôt a longtemps porté la note « aucun DAG n'est importable hors conteneur », avec
une conséquence directe et coûteuse : **un test qui passe par l'import skippe en
silence**, donc les seuils de collecte ont dû être déplacés dans `src/utils/` pour
être testables du tout, et rien ne vérifiait la structure des DAGs eux-mêmes.

Deux vestiges l'empêchaient, tous deux morts sur l'Airflow qui tourne réellement en
production (2.8.1) :

  * `schedule_interval=` — l'orthographe d'Airflow 1/2.3, remplacée par `schedule=`
    depuis la 2.4 et **supprimée** en 3.x ;
  * `provide_context=True` — un argument d'Airflow **1.x**, sans effet depuis la 2.0
    (le contexte est passé automatiquement) et rejeté en 3.x.

Les retirer ne change rien à l'exécution en 2.8.1 et débloque deux choses à la fois :
ce test, et la montée de version de l'image (R49b) — la PR Dependabot #100, qui
proposait 2.8.1 → 3.3.0, aurait fait échouer l'import des **16** DAGs, donc arrêté
toute la collecte.

Ce que ce garde vaut : il échoue sur une faute de frappe dans un DAG, sur un import
cassé, sur un opérateur mal construit — au moment du commit, plus au réveil du
scheduler.
"""
import importlib.util
import logging
import pathlib
import sys
import warnings

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DAGS = ROOT / "airflow" / "dags"

_DAG_FILES = sorted(p.name for p in DAGS.glob("*.py") if not p.name.startswith("_"))


def test_the_scope_is_not_empty():
    """Un garde qui ne trouve plus de DAG passe au vert sans rien vérifier."""
    assert len(_DAG_FILES) >= 16, (
        f"seulement {len(_DAG_FILES)} DAG(s) trouvé(s) dans {DAGS} — "
        "chemin faux, ou des DAGs ont disparu."
    )


@pytest.fixture(scope="module", autouse=True)
def _quiet_airflow():
    """Airflow parle beaucoup au premier import ; ça ne regarde pas ce test."""
    logging.disable(logging.CRITICAL)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        yield
    logging.disable(logging.NOTSET)


@pytest.mark.parametrize("name", _DAG_FILES, ids=_DAG_FILES)
def test_dag_imports(name: str):
    for extra in (str(ROOT), str(ROOT / "airflow")):
        if extra not in sys.path:
            sys.path.insert(0, extra)
    path = DAGS / name
    spec = importlib.util.spec_from_file_location(f"_dagtest_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 — on veut le type ET le message
        pytest.fail(
            f"{name} ne s'importe pas : {type(exc).__name__}: {exc}\n"
            "Le scheduler le découvrirait à sa prochaine relecture, en production."
        )


@pytest.mark.parametrize("name", _DAG_FILES, ids=_DAG_FILES)
def test_no_dead_airflow_1_argument(name: str):
    """`provide_context` ne fait rien depuis Airflow 2.0 et casse la 3.x."""
    source = (DAGS / name).read_text(encoding="utf-8")
    assert "provide_context" not in source, (
        f"{name} passe `provide_context`, un argument d'Airflow 1.x : sans effet sur "
        "l'Airflow 2.8.1 de production, et rejeté par la 3.x — il rendrait la montée "
        "de version impossible sans que rien ne le signale d'ici là."
    )


@pytest.mark.parametrize("name", _DAG_FILES, ids=_DAG_FILES)
def test_schedule_uses_the_spelling_that_survives(name: str):
    """`schedule_interval` est supprimé en Airflow 3 ; `schedule` marche des deux côtés."""
    source = (DAGS / name).read_text(encoding="utf-8")
    assert "schedule_interval" not in source, (
        f"{name} utilise `schedule_interval=`, supprimé en Airflow 3. `schedule=` est "
        "accepté depuis la 2.4, donc par la production comme par une future 3.x."
    )
