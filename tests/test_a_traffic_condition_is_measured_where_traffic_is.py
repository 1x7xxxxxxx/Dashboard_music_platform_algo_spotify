"""Une condition de réouverture qui parle de TRAFIC se mesure en production.

Type: Test
Uses: ast
Depends on: tools/dev/reopen_check.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Mesuré le 2026-09-20 : `_r116()` et `_r131()` appelaient `from_env_or_config()`, qui
depuis un poste de développement résout `localhost:5433`. Or `daily_ops_metrics` est
alimentée par le **DAG de production**. Les chiffres divergeaient :

                 local (ce que l'outil disait)   production (la vérité)
    R116              0 jour complet                    2
    R131              5 jours sur 30                    4

C'est l'outil **dont le rôle est de décider quand une tâche de roadmap revient**, et il
décidait sur une base qui ne porte pas le phénomène qu'il mesure. Il l'aurait fait
indéfiniment : rien ne rend ce défaut visible, puisque la requête réussit et rend un
nombre plausible.

⚠️ Le motif correct existait **déjà dans ce fichier** : `_r114()` passe par `PROD_SSH` et
LÈVE si la variable manque, plutôt que de conclure sur rien. Deux contrôles voisins, une
seule discipline appliquée — la forme exacte de `a-rule-copied-is-a-rule-that-will-diverge`.

⚠️ Et le remède n'est pas « mesurer la prod quoi qu'il arrive » : sans `PROD_SSH`, le
contrôle rend **INDÉCIDABLE**. Une condition indécidable n'est pas satisfaite, et elle
n'est pas refusée non plus — c'est la seule réponse honnête quand on n'a pas pu mesurer.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_OUTIL = ROOT / "tools" / "dev" / "reopen_check.py"

#: Les contrôles dont la grandeur est produite par le trafic de PRODUCTION.
_CONDITIONS_DE_TRAFIC = ("_r116", "_r131")


def _arbre() -> ast.Module:
    return ast.parse(_OUTIL.read_text(encoding="utf-8"))


def _appels_de(nom: str) -> set[str]:
    """Les fonctions appelées par ce contrôle, transitivement sur un niveau."""
    arbre = _arbre()
    fns = {n.name: n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef)}
    if nom not in fns:
        return set()
    vus: set[str] = set()
    for n in ast.walk(fns[nom]):
        if isinstance(n, ast.Call):
            appele = getattr(n.func, "id", "") or getattr(n.func, "attr", "")
            vus.add(appele)
            if appele in fns and appele != nom:
                for m in ast.walk(fns[appele]):
                    if isinstance(m, ast.Call):
                        vus.add(getattr(m.func, "id", "") or getattr(m.func, "attr", ""))
    return vus


@pytest.mark.parametrize("controle", _CONDITIONS_DE_TRAFIC)
def test_a_traffic_condition_does_not_read_the_local_database(controle: str) -> None:
    """LE GARDE. `from_env_or_config()` résout la base LOCALE depuis un poste de dev."""
    appels = _appels_de(controle)
    assert "from_env_or_config" not in appels, (
        f"`{controle}` lit la base via `from_env_or_config()`. Depuis un poste de "
        "développement, cela résout `localhost:5433` — et `daily_ops_metrics` est "
        "alimentée par le DAG de PRODUCTION. Le contrôle rendrait un nombre plausible "
        "et faux, indéfiniment.")


@pytest.mark.parametrize("controle", _CONDITIONS_DE_TRAFIC)
def test_a_traffic_condition_refuses_to_conclude_without_prod_access(controle: str) -> None:
    """Sans `PROD_SSH`, INDÉCIDABLE — jamais « en attente »."""
    texte = _OUTIL.read_text(encoding="utf-8")
    arbre = _arbre()
    fns = {n.name: n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef)}
    corps = "\n".join(
        ast.unparse(fns[n]) for n in ({controle} | _appels_de(controle)) & set(fns))
    assert "PROD_SSH" in corps, (
        f"`{controle}` ne demande pas `PROD_SSH`. Il conclura donc sur la base qu'il "
        "trouve, quelle qu'elle soit.")
    assert "RuntimeError" in corps, (
        f"`{controle}` ne LÈVE pas quand il ne peut pas mesurer. Le cadre transforme une "
        "exception en INDÉCIDABLE ; sans elle, le contrôle rendrait « en attente » — "
        "c'est-à-dire un verdict, sur rien.")
    assert texte.count("n'a RIEN vérifié") >= 2, (
        "le message qui dit qu'un contrôle n'a rien vérifié a disparu d'un des sites. "
        "C'est la phrase qui empêche de lire un INDÉCIDABLE comme un « pas encore ».")


def test_the_pattern_is_the_one_its_neighbour_already_used() -> None:
    """ANTI-VACUITÉ : `_r114` portait déjà la discipline. Elle doit y rester.

    Si `_r114` cessait d'exiger `PROD_SSH`, le garde ci-dessus resterait vert tout en
    ayant perdu son modèle — et la prochaine condition de trafic serait écrite sur le
    mauvais patron.
    """
    fns = {n.name: n for n in ast.walk(_arbre()) if isinstance(n, ast.FunctionDef)}
    assert "_r114" in fns, "`_r114` a disparu — mettre ce garde à jour"
    assert "PROD_SSH" in ast.unparse(fns["_r114"]), (
        "`_r114` n'exige plus `PROD_SSH`. C'est le contrôle qui portait la discipline "
        "avant les autres ; la perdre là, c'est perdre le modèle.")
