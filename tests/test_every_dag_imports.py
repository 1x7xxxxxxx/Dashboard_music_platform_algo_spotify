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
import ast
import importlib.util
import logging
import pathlib
import sys
import warnings

import pytest

from tests.dep_gate import requires

# Sans `apache-airflow` dans CET interpréteur, chacun des 16 imports échoue en
# `ImportError: cannot import name 'DAG' from 'airflow'` — 16 rouges qui disent
# « mauvais interpréteur », pas « DAG cassé ». Le piège : le dossier `airflow/` du
# dépôt est capté comme paquet-espace-de-noms, donc l'erreur ressemble à une
# installation corrompue. `dep_gate` distingue les deux, et `CI` ne peut pas
# emprunter ce chemin (voir `test_ci_never_skips_a_dependency_gate`).
_needs_airflow = requires("airflow")

ROOT = pathlib.Path(__file__).resolve().parents[1]
DAGS = ROOT / "airflow" / "dags"

_DAG_FILES = sorted(p.name for p in DAGS.glob("*.py") if not p.name.startswith("_"))


def test_the_scope_is_not_empty():
    """Un garde qui ne trouve plus de DAG passe au vert sans rien vérifier."""
    # 12 et non 10 : c'est le compte EXACT après la suppression des quatre
    # `*_csv_watcher` le 2026-09-04. Un plancher avec du mou laisserait deux
    # disparitions de plus passer inaperçues, et ce garde existe pour ça.
    assert len(_DAG_FILES) >= 12, (
        f"seulement {len(_DAG_FILES)} DAG(s) trouvé(s) dans {DAGS} — "
        "chemin faux, ou des DAGs ont disparu."
    )


_DEAD_KWARGS = {
    "provide_context": "Airflow 1.x, sans effet depuis 2.0, rejeté par la 3.x",
    "schedule_interval": "supprimé en Airflow 3 ; `schedule=` marche des deux côtés",
}


def dead_arguments(source: str) -> list[tuple[str, int]]:
    """(keyword, line) of every Airflow argument dead in 3.x PASSED to a call. Pure.

    AST, not text: a comment or a docstring explaining why the argument was removed
    must not fail the guard of that removal.
    """
    return sorted((kw.arg, node.lineno) for node in ast.walk(ast.parse(source))
                  if isinstance(node, ast.Call) for kw in node.keywords
                  if kw.arg in _DEAD_KWARGS)


@pytest.fixture(scope="module")
def _quiet_airflow():
    """Airflow parle beaucoup au premier import ; ça ne regarde pas ce test."""
    logging.disable(logging.CRITICAL)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        yield
    logging.disable(logging.NOTSET)


@_needs_airflow
@pytest.mark.parametrize("name", _DAG_FILES, ids=_DAG_FILES)
def test_dag_imports(name: str, _quiet_airflow):
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
def test_no_argument_that_airflow_3_rejects(name: str):
    """`provide_context` (1.x) and `schedule_interval` (removed in 3.x) — the two
    vestiges that would have failed the import of all 16 DAGs on Dependabot's #100."""
    dead = dead_arguments((DAGS / name).read_text(encoding="utf-8"))
    assert not dead, (
        f"{name} passe {[f'{k} (ligne {ln}) — {_DEAD_KWARGS[k]}' for k, ln in dead]}. "
        "Sans effet visible sur la production d'aujourd'hui, et c'est ce qui rendrait "
        "la montée de version impossible sans que rien ne le signale d'ici là.")


def test_the_detector_sees_the_defect_it_is_written_for():
    """Non-vacuity, without Airflow: both vestiges passed as arguments are named; the
    surviving spelling, and a comment naming the dead one, are not."""
    defect = ("DAG('x', schedule_interval='@daily')\n"
              "PythonOperator(task_id='t', python_callable=f, provide_context=True)\n")
    assert dead_arguments(defect) == [("provide_context", 2), ("schedule_interval", 1)]
    fixed = ("# schedule_interval= was removed in Airflow 3; provide_context too\n"
             "DAG('x', schedule='@daily')\n"
             "PythonOperator(task_id='t', python_callable=f)\n")
    assert dead_arguments(fixed) == []
