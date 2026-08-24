"""La frontière HTTP a UNE sortie, nommée, et elle ne se propage pas.

Classe `boundary-with-no-named-exit-kills-what-must-pass`.

`tests/conftest.py::_no_real_http` est `autouse` : aucun test ne sort sur le réseau.
C'est la bonne règle — mesuré le 2026-08-23, un test de préflight ouvrait quatre
connexions réelles vers Meta, Google et SoundCloud avec les credentials de `.env`.

Mais une frontière sans exception nommée n'éteint pas que ce qu'elle vise. Mesuré le
2026-08-24 sur la CI de production : `tests/test_prod_health.py` — dont le rôle est
de sonder l'application LIVE à travers Cloudflare, l'une des trois épaisseurs du
filet de surveillance — rendait **14 failed, 14 errors** chaque matin depuis que la
frontière existe. La suite se gardait pourtant déjà elle-même (`RUN_PROD_HEALTH=1`,
sinon elle skippe) : c'est la frontière qui l'écrasait au niveau SOCKET, sous son
propre garde. Son rouge quotidien se lisait comme du bruit.

Deux invariants sont gardés ici :

1. **La sortie reste unique.** Une échappatoire qui se répand redevient l'absence de
   frontière. Ajouter un fichier à la liste ci-dessous doit être un geste conscient.
2. **`pytestmark` ne s'affecte qu'une fois.** Deux affectations successives ne se
   combinent pas : la seconde écrase la première, en silence, et le marqueur perdu ne
   manque à personne. C'est arrivé dans ce dépôt le jour même où le marqueur a été
   introduit.
"""
import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

# Les SEULS fichiers autorisés à sortir sur le réseau. Un ajout ici se justifie dans
# le message de commit : la question n'est pas « ce test a-t-il besoin du réseau ? »
# mais « son objet EST-IL le réseau ? ».
_ALLOWED_REAL_HTTP = {"test_prod_health.py"}


def _marked_real_http(path: pathlib.Path) -> bool:
    """Le fichier porte-t-il le MARQUEUR `real_http` (pytestmark ou décorateur) ?

    AST, jamais une sous-chaîne. La première version de ce test cherchait
    `"real_http" in source` et accusait `test_the_suite_cannot_call_an_api.py`, qui
    ne fait que **nommer** la fixture `_no_real_http` et sa propre fonction
    `test_a_test_cannot_open_a_real_http_connection`. C'est la classe
    `guard-seeded-by-prose-not-by-code`, cataloguée une heure plus tôt le même jour
    et aussitôt réintroduite : le réflexe du `in source` est tenace, et il produit
    ici la pire forme de faux positif — celle qui accuse le garde d'à côté.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))

    def _is_the_mark(node) -> bool:
        # `pytest.mark.real_http` — un Attribute dont le nom final est le marqueur
        # et dont la base est bien `pytest.mark`.
        return (isinstance(node, ast.Attribute) and node.attr == "real_http"
                and isinstance(node.value, ast.Attribute) and node.value.attr == "mark")

    for node in ast.walk(tree):
        if _is_the_mark(node):
            return True
    return False


def test_only_the_production_probe_may_leave_the_boundary():
    marked = {p.name for p in TESTS.rglob("test_*.py") if _marked_real_http(p)}
    marked.discard(pathlib.Path(__file__).name)  # ce fichier PARLE du marqueur
    assert marked == _ALLOWED_REAL_HTTP, (
        f"la sortie de la frontière HTTP s'est élargie : {sorted(marked)} "
        f"(attendu : {sorted(_ALLOWED_REAL_HTTP)}). Une échappatoire qui se propage "
        "redevient l'absence de frontière — si l'ajout est voulu, l'inscrire ici et "
        "le dire dans le commit."
    )


def test_the_boundary_still_declares_its_exit():
    """Le nom du marqueur vit à UN endroit ; le renommer sans le dire le désactive."""
    conftest = (TESTS / "conftest.py").read_text(encoding="utf-8")
    assert '_REAL_HTTP_MARK = "real_http"' in conftest, (
        "tests/conftest.py ne déclare plus la sortie nommée `real_http` : soit la "
        "frontière n'a plus d'exception (et la sonde de production remeurt), soit "
        "elle en a une qui ne porte plus ce nom."
    )
    assert "get_closest_marker(_REAL_HTTP_MARK)" in conftest, (
        "le marqueur est déclaré mais la frontière ne le consulte plus."
    )


def _pytestmark_assignments(path: pathlib.Path) -> list:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n.lineno for n in tree.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in n.targets)]


_TEST_FILES = sorted(p.relative_to(ROOT).as_posix() for p in TESTS.rglob("test_*.py"))


@pytest.mark.parametrize("rel", _TEST_FILES, ids=_TEST_FILES)
def test_pytestmark_is_assigned_at_most_once(rel: str):
    """Deux affectations ne se combinent pas — la seconde efface la première."""
    lines = _pytestmark_assignments(ROOT / rel)
    assert len(lines) <= 1, (
        f"{rel} affecte `pytestmark` {len(lines)} fois (lignes {lines}). La dernière "
        "écrase les précédentes sans avertissement : les marqueurs perdus cessent "
        "simplement de s'appliquer. Réunir en une seule LISTE."
    )
