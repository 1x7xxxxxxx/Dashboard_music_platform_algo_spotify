"""Un test ne dépend ni du répertoire courant, ni de l'état de la base locale.

Type: Test
Uses: pytest, ast
Depends on: tests/
Persists in: nothing

Ce qui a été mesuré (2026-09-10)
--------------------------------
Huit tests VERTS en local et ROUGES en CI, pour deux raisons distinctes — et la CI
rouge est le pire des états, parce qu'elle cache tout ce qui vient après elle. Ce dépôt
a déjà perdu 8 exécutions puis 27 de cette façon.

**Cinq** venaient d'un locataire technique que le test SUPPOSAIT : `s4a_song_timeline`
porte une clé étrangère vers `saas_artists`, et l'identifiant employé existait dans la
base de développement — posé à la main un jour — et nulle part ailleurs. Le test ne
prouvait pas que le mécanisme marche : il prouvait que CETTE base avait cet état.

**Trois** venaient d'un chemin RELATIF donné à l'harnais Streamlit, qui le résout
depuis le fichier appelant : `tests/` + `src/dashboard/app.py` = `tests/src/dashboard/…`,
qui n'existe pas. Il ne marchait en local que par la grâce de la version installée.

Ce que ce garde ferme
----------------------
La seconde moitié, qui est mécaniquement vérifiable. La première l'est par le fait que
chaque test crée désormais son propre locataire — un garde générique exigerait de
distinguer « suppose » de « crée », ce qu'un prédicat ne sait pas faire honnêtement.
"""
from __future__ import annotations

import ast
from pathlib import Path

TESTS = Path(__file__).resolve().parent


def test_no_apptest_is_given_a_relative_path() -> None:
    """`AppTest.from_file` reçoit un chemin absolu, toujours.

    Structurel : on lit l'ARGUMENT de l'appel, pas le texte du fichier. Une chaîne
    littérale qui ne commence pas par `/` est relative — et sera résolue depuis
    `tests/`, donc à côté.
    """
    offenders: list[str] = []
    for f in sorted(TESTS.glob("test_*.py")):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "from_file"):
                continue
            if not node.args:
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if not arg.value.startswith("/"):
                    offenders.append(f"{f.name}:{node.lineno} → {arg.value!r}")

    assert not offenders, (
        "chemin relatif donné à `AppTest.from_file` : " + ", ".join(offenders)
        + ". Il est résolu depuis le fichier appelant, donc depuis `tests/`, et le "
          "test devient vert ou rouge selon le répertoire d'où on le lance et selon "
          "la version de Streamlit installée. Dériver le chemin de la racine du dépôt.")


def test_the_predicate_sees_the_calls_it_claims_to_watch() -> None:
    """Non-vacuité : sans appel trouvé, le garde serait vert pour toujours."""
    seen = 0
    for f in TESTS.glob("test_*.py"):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        seen += sum(1 for n in ast.walk(tree)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "from_file")
    assert seen >= 3, f"seulement {seen} appel(s) à `from_file` vu(s) — prédicat cassé"
