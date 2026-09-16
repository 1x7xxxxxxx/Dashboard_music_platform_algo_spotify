"""Un garde qui écarte les docstrings doit réellement en écarter.

Type: Test
Uses: ast, pathlib
Depends on: tests/*.py
Persists in: nothing

Ce qui a été mesuré
-------------------
2026-09-16. Un garde venait d'être converti de « lire le texte » à « lire l'AST », pour
satisfaire `test_a_guard_reads_structure_not_text`. Il cherchait des littéraux de chaîne
DANS DU CODE, et écartait donc les docstrings ainsi :

    docstrings = {ast.get_docstring(n) for n in ast.walk(tree) if ...}
    literals = {n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and n.value not in docstrings}

**`ast.get_docstring()` nettoie et DÉSINDENTE par défaut** (`clean=True`), alors que le
nœud `Constant` porte le texte brut, indentation comprise. Les deux ne sont donc jamais
égaux : l'exclusion ne retire rien, et la docstring du module suffit à satisfaire
n'importe quelle recherche de littéral. Mesuré — la mutation
`_get("/api/v1/rules")` → `_get("/api/v1/alerts")` est passée VERTE, parce que la
docstring du module cite `/api/v1/rules`.

Le garde avait l'air rigoureux, il lisait bien l'AST, et il ne gardait rien. Lire l'AST
ne suffit pas : il faut lui poser une question à laquelle il peut répondre.

Ce que ce test assert
---------------------
Pour chaque fichier de test qui construit un ensemble nommé `docstrings` et le compare
PAR VALEUR, l'appel à `get_docstring` doit passer `clean=False`. Deux fichiers du dépôt
le font déjà explicitement et sont corrects — le garde ne les accuse pas.

L'autre forme correcte, celle qu'on préfère, compare par IDENTITÉ DE NŒUD
(`id(node) not in docstrings`) : elle ne dépend d'aucun nettoyage, et six fichiers du
dépôt l'utilisent. Elle ne déclenche rien ici.
"""
from __future__ import annotations

import ast
from pathlib import Path

_TESTS = Path(__file__).resolve().parent


def _compares_by_value(tree: ast.AST) -> list[int]:
    """Les lignes où un `.value` est comparé à un ensemble nommé `docstrings`."""
    hits = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Compare):
            continue
        if not any(isinstance(op, (ast.NotIn, ast.In)) for op in n.ops):
            continue
        right = n.comparators[0] if n.comparators else None
        if not (isinstance(right, ast.Name) and right.id == "docstrings"):
            continue
        left = n.left
        # `id(x) not in docstrings` est la forme CORRECTE : on ne la compte pas.
        if isinstance(left, ast.Call) and isinstance(left.func, ast.Name) \
                and left.func.id == "id":
            continue
        hits.append(n.lineno)
    return hits


def _unclean_get_docstring(tree: ast.AST) -> list[int]:
    """Les appels à `get_docstring` qui laissent `clean` à son défaut (True)."""
    hits = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        fn = n.func
        name = fn.attr if isinstance(fn, ast.Attribute) else (
            fn.id if isinstance(fn, ast.Name) else None)
        if name != "get_docstring":
            continue
        if not any(kw.arg == "clean" for kw in n.keywords):
            hits.append(n.lineno)
    return hits


def test_no_docstring_exclusion_compares_dedented_text() -> None:
    offenders = []
    for path in sorted(_TESTS.glob("test_*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        by_value = _compares_by_value(tree)
        if not by_value:
            continue
        unclean = _unclean_get_docstring(tree)
        if unclean:
            offenders.append(
                f"{path.name} : comparaison par valeur ligne(s) {by_value}, "
                f"`get_docstring()` sans `clean=False` ligne(s) {unclean}")

    assert not offenders, (
        "exclusion de docstrings VIDE — elle n'écarte rien :\n  "
        + "\n  ".join(offenders)
        + "\n\n`ast.get_docstring()` DÉSINDENTE par défaut ; le nœud `Constant` porte le "
          "texte brut. Les deux ne sont jamais égaux, donc la docstring du module "
          "satisfait n'importe quelle recherche de littéral et le garde est vert sur son "
          "propre défaut.\n"
          "Deux corrections, l'une meilleure que l'autre :\n"
          "  • comparer par IDENTITÉ — `id(node) not in docstrings` — qui ne dépend "
          "d'aucun nettoyage ;\n"
          "  • ou passer `clean=False` explicitement, si la comparaison par valeur est "
          "voulue.")


def test_the_detector_sees_both_halves() -> None:
    """Non-vacuité : sur le code EXACT du défaut, le détecteur doit mordre.

    Et il ne doit pas mordre sur les deux formes correctes, sinon corriger un garde le
    ferait rougir — la leçon que ce dépôt a apprise en voyant un garde passer au rouge
    sur le commentaire de son propre correctif.
    """
    defect = ast.parse(
        "import ast\n"
        "docstrings = {ast.get_docstring(n) for n in ast.walk(t)}\n"
        "lits = [n.value for n in ast.walk(t) if n.value not in docstrings]\n")
    assert _compares_by_value(defect), "la comparaison par valeur n'est pas vue"
    assert _unclean_get_docstring(defect), "`clean` laissé par défaut n'est pas vu"

    ok_clean = ast.parse(
        "import ast\n"
        "docstrings = {ast.get_docstring(n, clean=False) for n in ast.walk(t)}\n"
        "lits = [n.value for n in ast.walk(t) if n.value not in docstrings]\n")
    assert _compares_by_value(ok_clean)
    assert not _unclean_get_docstring(ok_clean), "`clean=False` est accusé à tort"

    ok_id = ast.parse(
        "import ast\n"
        "docstrings = {id(n.body[0].value) for n in ast.walk(t)}\n"
        "lits = [n.value for n in ast.walk(t) if id(n) not in docstrings]\n")
    assert not _compares_by_value(ok_id), "la comparaison par identité est accusée à tort"
