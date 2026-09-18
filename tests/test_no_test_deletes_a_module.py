"""
Guard — a test may borrow global state, never leave a hole where it found something.

Type: Sub
Uses: ast, pathlib
Triggers: pytest
Depends on: tests/**
Persists in: nothing

Error class: test-leaves-a-hole-in-sys-modules.

Measured 2026-08-23. `tests/test_readiness_carries_the_live_diagnosis.py` stubbed
`sys.modules["src.dashboard.views.credentials._registry"]` and, in its `finally`, called
`del` instead of restoring the previous value. Deleting the key evicts the real module
for the REST OF THE SESSION: the next import re-executes it from disk and hands out a
second module object, while everything that already did `from … import NAME` keeps the
first. A later `monkeypatch.setattr("pkg.mod.NAME", …)` then patches one object while the
code under test reads the other.

The symptom in CI was `test_a_raising_probe_becomes_a_red_not_a_traceback` failing with
the five REAL probes in its output, despite a monkeypatch to a single fake one — a test
that had nothing to do with the offender, in a different file.

This trap is invisible to any single-file run, because the test that causes it always
passes. That is why it needs a structural guard rather than a test.
"""

import ast
from pathlib import Path

import pytest

# Ce fichier mute un état de PROCESSUS partagé (sys.modules, un attribut de
# classe, un fichier du dépôt). Sous `--dist loadgroup` ses tests restent donc
# sur UN worker, comme le faisait `--dist loadfile` pour tout le monde.
# Voir `.claude/dev-docs/test-suite-performance.md` et R110.
pytestmark = pytest.mark.xdist_group("no-test-deletes-a-module")

TESTS = Path(__file__).resolve().parent


def _test_files() -> list[str]:
    return sorted(p.name for p in TESTS.glob("test_*.py"))


def _saves_previous(portee: ast.AST) -> bool:
    """`sys.modules.get(...)` — la sauvegarde qui rend le `pop` légitime."""
    return any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "get"
        and isinstance(n.func.value, ast.Attribute)
        and n.func.value.attr == "modules"
        for n in ast.walk(portee)
    )


def _portees(tree: ast.AST) -> list:
    """Chaque fonction de premier niveau, plus le module hors fonctions.

    ⚠️ **La portée est la FONCTION, pas le fichier, depuis le 2026-09-18.**
    `saves_previous` parcourait `ast.walk(tree)` — donc tout le fichier. Un fichier
    portant UNE fonction correcte (`previous = sys.modules.get(k)`) et une AUTRE qui
    fait `sys.modules.pop(k, None)` sans rien sauver passait au vert : la sauvegarde
    de la première absolvait la seconde. Le prédicat répondait « ce FICHIER sauve
    quelque part » là où la propriété est « CETTE fonction rend ce qu'elle a pris ».
    Aucun fichier n'exploitait le trou, et c'est justement pour ça qu'il fallait le
    fermer avant qu'un le fasse.
    """
    fonctions = [n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    dans_une_fonction = {id(x) for f in fonctions for x in ast.walk(f)}
    hors = [n for n in ast.walk(tree) if id(n) not in dans_une_fonction]
    return fonctions + [hors]


def _evictions(path: Path) -> list[int]:
    """`del sys.modules[…]`, and `sys.modules.pop` with no saved previous value."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad: list[int] = []

    for portee in _portees(tree):
        noeuds = list(ast.walk(portee)) if not isinstance(portee, list) else portee
        # A function that saves the previous value is doing the right thing; the `pop`
        # in its restore branch is the correct ending, not the defect.
        sauve = any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "get"
            and isinstance(n.func.value, ast.Attribute)
            and n.func.value.attr == "modules"
            for n in noeuds
        )
        for node in noeuds:
            if isinstance(node, ast.Delete):
                for tgt in node.targets:
                    if (isinstance(tgt, ast.Subscript)
                            and isinstance(tgt.value, ast.Attribute)
                            and tgt.value.attr == "modules"):
                        bad.append(node.lineno)
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "pop"
                    and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr == "modules"
                    and not sauve):
                bad.append(node.lineno)
    return sorted(set(bad))


def test_the_scope_is_not_empty() -> None:
    assert len(_test_files()) > 50, "the test walk found almost nothing"


@pytest.mark.parametrize("name", _test_files())
def test_a_test_restores_what_it_borrows_from_sys_modules(name: str) -> None:
    bad = _evictions(TESTS / name)
    assert not bad, (
        f"{name} removes an entry from sys.modules at line(s) {bad} instead of restoring "
        f"the previous value. That evicts the real module for the rest of the session, "
        f"and the next import hands out a SECOND object — so a later monkeypatch patches "
        f"one while the code reads the other. Save it first:\n"
        f"    previous = sys.modules.get(key)\n"
        f"    ...\n"
        f"    if previous is not None: sys.modules[key] = previous\n"
        f"    else: sys.modules.pop(key, None)"
    )


def test_the_detector_sees_the_eviction_it_is_written_for(tmp_path: Path) -> None:
    """Non-vacuité : sur le code EXACT du défaut, `_evictions` doit mordre.

    Le paramétré ci-dessus est vert sur ~170 fichiers propres, et il resterait vert
    mot pour mot si `_evictions` rendait toujours `[]`. C'est la forme d'aveuglement
    la plus coûteuse du dépôt : un garde qu'on croit tendu sur toute la suite alors
    qu'il ne regarde rien. On lui soumet donc les deux moitiés — la forme interdite,
    puis la forme CORRIGÉE, qui doit rester muette sous peine de rendre la
    correction impossible sans désarmer le garde.
    """
    defect = tmp_path / "test_evicts.py"
    defect.write_text(
        "import sys\n"
        "\n"
        "def test_x():\n"
        "    del sys.modules['src.utils.config_loader']\n"
        "    sys.modules.pop('src.database.postgres_handler', None)\n",
        encoding="utf-8",
    )
    assert _evictions(defect) == [4, 5], (
        f"le détecteur rend {_evictions(defect)} sur un fichier qui supprime DEUX "
        "entrées de sys.modules noir sur blanc : il ne garde plus rien, et les "
        "~170 cas paramétrés sont verts par cécité.")

    restored = tmp_path / "test_restores.py"
    restored.write_text(
        "import sys\n"
        "\n"
        "def test_x():\n"
        "    previous = sys.modules.get('src.utils.config_loader')\n"
        "    try:\n"
        "        pass\n"
        "    finally:\n"
        "        if previous is not None:\n"
        "            sys.modules['src.utils.config_loader'] = previous\n"
        "        else:\n"
        "            sys.modules.pop('src.utils.config_loader', None)\n",
        encoding="utf-8",
    )
    assert _evictions(restored) == [], (
        f"le détecteur rend {_evictions(restored)} sur la forme CORRIGÉE — celle "
        "que le message d'erreur ci-dessus recommande littéralement. Suivre le "
        "conseil du garde ferait rougir le garde.")


def test_the_scope_is_the_function_not_the_file(tmp_path):
    """La preuve que ce fichier se donne : une fonction saine n'absout pas sa voisine.

    Mesuré le 2026-09-18 en balayant les frères de `test-leaves-a-hole-in-sys-modules`.
    `saves_previous` parcourait `ast.walk(tree)` — tout le FICHIER. Un fichier portant
    une fonction correcte et une fonction fautive passait donc au vert : la sauvegarde
    de la première couvrait la seconde.

    Aucun fichier du dépôt n'exploitait ce trou le jour où il a été trouvé, et c'est
    exactement pour ça qu'il fallait le fermer — un garde qu'on ne peut pas voir
    échouer est un garde qu'on croit sur parole.
    """
    fichier = tmp_path / "test_deux_fonctions.py"
    fichier.write_text(
        "import sys\n"
        "\n"
        "def test_correcte():\n"
        "    precedent = sys.modules.get('json')\n"
        "    try:\n"
        "        pass\n"
        "    finally:\n"
        "        if precedent is None:\n"
        "            sys.modules.pop('json', None)\n"
        "\n"
        "def test_fautive():\n"
        "    sys.modules.pop('csv', None)\n",
        encoding="utf-8")
    trouve = _evictions(fichier)
    assert trouve == [12], (
        f"la fonction fautive (ligne 12) n'est pas vue : {trouve}. Le prédicat répond "
        "« ce FICHIER sauve quelque part » là où la propriété est « CETTE fonction rend "
        "ce qu'elle a pris ».")


def test_a_lone_correct_function_is_not_flagged(tmp_path):
    """Et l'inverse : le correctif ne doit pas devenir un faux positif."""
    fichier = tmp_path / "test_une_fonction.py"
    fichier.write_text(
        "import sys\n"
        "\n"
        "def test_correcte():\n"
        "    precedent = sys.modules.get('json')\n"
        "    try:\n"
        "        pass\n"
        "    finally:\n"
        "        if precedent is None:\n"
        "            sys.modules.pop('json', None)\n",
        encoding="utf-8")
    assert _evictions(fichier) == [], (
        "le prédicat mord sur la forme CORRECTE — il rendrait l'arbre rouge en "
        "permanence")


def test_module_level_eviction_is_still_seen(tmp_path):
    """Un `pop` hors de toute fonction reste couvert — c'est le pire des cas."""
    fichier = tmp_path / "test_au_module.py"
    fichier.write_text("import sys\nsys.modules.pop('csv', None)\n", encoding="utf-8")
    assert _evictions(fichier) == [2], (
        "un `pop` au niveau du MODULE échappe au découpage par fonction — il s'exécute "
        "à l'import, donc avant tout test, et c'est la forme la plus dommageable")
