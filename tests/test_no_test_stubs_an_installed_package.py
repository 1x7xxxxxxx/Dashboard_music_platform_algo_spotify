"""Personne ne remplace par un mock un paquet qui est réellement installé.

Classe `session-wide-stub-of-an-installed-package`.

Deux fichiers de test posaient, **à la collecte** et sans jamais restaurer :

    sys.modules["spotipy"] = MagicMock()
    sys.modules["googleapiclient"] = MagicMock()
    sys.modules["airflow.operators"] = MagicMock()

La justification écrite était « ils vivent dans l'image Airflow, pas dans le venv de
dev ou de CI ». Elle a cessé d'être vraie sans que personne le remarque : les quatre
paquets sont des dépendances déclarées du projet.

Deux dégâts, de gravités différentes :

  * **le silencieux** — un test qui croit exercer le vrai client travaille contre un
    mock et passe au vert sans rien prouver ;
  * **le bruyant, mais tardif** — un import légitime d'un sous-module échoue plus
    loin sur « 'airflow.operators' is not a package ». Mesuré le 2026-08-24 : quatre
    DAGs tombaient en exécution GROUPÉE et passaient isolément, la signature exacte
    d'une dépendance à l'ordre.

Le helper reste légitime pour un paquet réellement absent — c'est la raison d'être du
prédicat ci-dessous, qui ne regarde pas *qu'on stube*, mais *qu'on stube quelque chose
d'installé*.
"""
import ast
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"


def _stubbed_names(path: pathlib.Path) -> set:
    """Les noms de modules passés à `_stub_module(...)` ou écrits dans `sys.modules`."""
    names = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        # _stub_module("x") / _stub_module(_mod) dans une boucle littérale
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "_stub_module"):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    names.add(arg.value)
        # for _mod in ("a", "b"): _stub_module(_mod)
        if isinstance(node, ast.For) and "_stub_module" in ast.dump(node):
            for elt in ast.walk(node.iter):
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    names.add(elt.value)
        # sys.modules["x"] = ... / sys.modules.setdefault("x", ...)
        if isinstance(node, ast.Subscript) and "sys" in ast.dump(node.value):
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                names.add(node.slice.value)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "setdefault" and "modules" in ast.dump(node.func)):
            for arg in node.args[:1]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    names.add(arg.value)
    return names


_FILES = sorted(p.relative_to(ROOT).as_posix() for p in TESTS.rglob("test_*.py"))


def test_the_scope_is_not_empty():
    assert len(_FILES) > 100, f"portée suspecte : {len(_FILES)} fichiers"


@pytest.mark.parametrize("rel", _FILES, ids=_FILES)
def test_no_installed_package_is_replaced_by_a_mock(rel: str):
    if rel == pathlib.Path(__file__).relative_to(ROOT).as_posix():
        return  # ce fichier NOMME les paquets, il n'en stube aucun
    offenders = []
    for name in _stubbed_names(ROOT / rel):
        root_pkg = name.split(".")[0]
        try:
            installed = importlib.util.find_spec(root_pkg) is not None
        except (ImportError, ValueError):  # pragma: no cover - defensive
            installed = False
        if installed:
            offenders.append(name)
    assert not offenders, (
        f"{rel} remplace par un mock des paquets INSTALLÉS : {sorted(offenders)}. "
        "Le stub vaut pour un paquet absent ; sur un paquet présent il rend le test "
        "vacant et casse les imports du reste de la session (il n'est jamais "
        "restauré)."
    )
