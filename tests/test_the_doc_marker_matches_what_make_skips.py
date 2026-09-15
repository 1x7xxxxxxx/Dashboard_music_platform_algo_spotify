"""Le marqueur `docs` et la liste que `make test-fast` saute disent la même chose.

Type: Test
Uses: pytest, ast, re
Depends on: Makefile (DOC_TESTS), pyproject.toml (markers), tests/test_*.py
Persists in: nothing

Ce qui a été mesuré (2026-09-15)
--------------------------------
`make test-fast` retire les tests qui ne lisent QUE des documents : 38,2 s, dont
**32 s pour le seul `test_the_gold_coverage_only_improves.py`**, qui recalcule
toute la carte de la couche or.

La liste doit être en clair dans le Makefile, et pas dérivée du marqueur, pour une
raison mesurée : `-m "not docs"` **collecte d'abord et désélectionne ensuite**,
donc il ne fait pas économiser le coût dominant — seul `--ignore`, qui agit avant
la collecte, le fait. Le prix de ce choix est que la même information vit à deux
endroits.

C'est exactement la forme qui dérive : on marque un cinquième fichier, on oublie la
liste, et `make test-fast` le lance quand même — ou pire, on retire un marqueur et
`make test` cesse de couvrir ce que `test-docs` croit couvrir. Ce fichier interdit
les deux sens.

Et la ROADMAP ne doit JAMAIS entrer dans cette liste
----------------------------------------------------
`test_roadmap_index_is_honest.py`, `test_roadmap_two_files.py` et
`test_the_resume_header_is_checked.py` ne lisent eux aussi que des `.md` — mais ils
tiennent l'état que `/resume` lit EN PREMIER. Le 2026-09-15 au matin, ce fichier
annonçait une tâche ouverte close depuis cinq jours, et rien ne l'avait vu. Les
sauter par défaut rendrait ce défaut structurellement invisible.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MAKEFILE = REPO / "Makefile"
PYPROJECT = REPO / "pyproject.toml"
TESTS = REPO / "tests"

# Les gardes de la roadmap : jamais marqués, jamais sautés, quoi qu'ils lisent.
_ROADMAP_GUARDS = frozenset({
    "test_roadmap_index_is_honest.py",
    "test_roadmap_two_files.py",
    "test_the_resume_header_is_checked.py",
})


def _make_list() -> set[str]:
    """Les fichiers que `DOC_TESTS` nomme dans le Makefile."""
    text = MAKEFILE.read_text(encoding="utf-8")
    m = re.search(r"^DOC_TESTS\s*:=(.*?)(?=^\w|\Z)", text, re.M | re.S)
    if not m:
        pytest.fail("`DOC_TESTS` a disparu du Makefile : `make test-fast` ne sait "
                    "plus quoi sauter, et ce garde ne sait plus quoi comparer.")
    return {Path(tok).name for tok in re.findall(r"tests/\S+\.py", m.group(1))}


def _marked_docs() -> set[str]:
    """Les fichiers portant `pytestmark = pytest.mark.docs`, lus par AST."""
    found = set()
    for f in sorted(TESTS.glob("test_*.py")):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(getattr(t, "id", None) == "pytestmark" for t in node.targets):
                continue
            if "pytest.mark.docs" in ast.unparse(node.value):
                found.add(f.name)
    return found


def test_the_two_lists_are_the_same():
    """Un fichier marqué mais non sauté, ou sauté mais non marqué, est une dérive."""
    in_make, marked = _make_list(), _marked_docs()

    assert marked - in_make == set(), (
        f"{sorted(marked - in_make)} portent le marqueur `docs` mais ne sont PAS "
        "dans `DOC_TESTS` du Makefile : `make test-fast` les lance quand même, et "
        "le marqueur ment sur ce qui est sauté."
    )
    assert in_make - marked == set(), (
        f"{sorted(in_make - marked)} sont sautés par `make test-fast` mais ne "
        "portent pas le marqueur `docs`. Soit ils lisent autre chose que des "
        "documents — et les sauter retire une vraie couverture — soit le marqueur "
        "manque."
    )


def test_no_roadmap_guard_is_ever_skipped():
    """La roadmap tourne toujours : c'est l'état d'où part chaque séance."""
    in_make, marked = _make_list(), _marked_docs()
    caught = sorted((in_make | marked) & _ROADMAP_GUARDS)

    assert not caught, (
        f"{caught} seraient sautés par `make test-fast`. Ces gardes tiennent le "
        "fichier que `/resume` lit EN PREMIER ; le 2026-09-15 il annonçait une "
        "tâche ouverte close depuis cinq jours. Les sauter par défaut rendrait "
        "cette classe de défaut structurellement invisible."
    )


def test_the_marker_is_declared():
    """Un marqueur non déclaré passe en silence sous `--strict-markers`."""
    assert re.search(r'^\s*"docs:', PYPROJECT.read_text(encoding="utf-8"), re.M), (
        "le marqueur `docs` n'est plus déclaré dans `[tool.pytest.ini_options]` de "
        "pyproject.toml : une faute de frappe dans un `pytestmark` ne serait plus "
        "signalée."
    )


def test_both_extractions_actually_find_something():
    """Non-vacuité : deux lectures vides seraient d'accord et ne prouveraient rien.

    C'est le mode d'échec silencieux de ce garde — si `_make_list` ou
    `_marked_docs` cesse de lire (motif cassé, `DOC_TESTS` renommé, AST changé),
    les deux ensembles deviennent vides, leur différence aussi, et
    `test_the_two_lists_are_the_same` passe sur du néant.
    """
    in_make, marked = _make_list(), _marked_docs()
    assert len(in_make) >= 3, (
        f"`DOC_TESTS` ne rend que {len(in_make)} fichier(s) : l'extraction du "
        "Makefile est probablement cassée."
    )
    assert len(marked) >= 3, (
        f"seulement {len(marked)} fichier(s) portent le marqueur `docs` : "
        "l'extraction AST est probablement cassée."
    )
    assert _ROADMAP_GUARDS <= {f.name for f in TESTS.glob("test_*.py")}, (
        "les gardes de roadmap nommés ici n'existent plus sous ces noms : "
        f"{sorted(_ROADMAP_GUARDS - {f.name for f in TESTS.glob('test_*.py')})}. "
        "`test_no_roadmap_guard_is_ever_skipped` protège alors des fantômes."
    )
