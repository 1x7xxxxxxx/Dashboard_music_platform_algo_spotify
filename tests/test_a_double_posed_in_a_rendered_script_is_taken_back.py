"""Une doublure posée dans un script `AppTest` est rendue avant la fin du script.

Type: Test
Uses: pytest, ast
Depends on: tests/*.py (les scripts passés à `AppTest.from_string`)
Persists in: nothing

Ce qui a été mesuré
-------------------
`AppTest.from_string` n'ouvre PAS de processus : il exécute le script dans celui des
tests, et partage donc `sys.modules` avec lui. Une affectation nue sur un module —
`m._share_state_cached = lambda ...` — survit donc au test qui l'a posée, et tous les
tests suivants du MÊME worker voient la doublure.

Trois occurrences dans ce dépôt, trouvées à trois dates différentes :

* `test_a_page_asks_the_same_question_once.py` — `read_setup_state` doublé sans
  rétablissement. Conséquence mesurée en CI le 2026-09-11 :
  `test_the_tab_bar_skips_what_is_done` trouvait l'onglet « 📂 Mes fichiers » VERT
  pour un locataire qui venait d'être créé vide ;
* `test_a_printed_command_is_runnable_as_printed.py` — `fernet_state` doublé ;
* `test_the_share_step_is_hidden_when_there_is_nothing_to_share.py` — état de partage
  doublé, corrigé le 2026-09-15, trouvé par un balayage de frères et **pas** par un
  test rouge : la pollution ne fait rougir que le voisin, jamais le coupable.

Les deux premières ont été corrigées une par une, à la main, sans que rien n'empêche
la troisième. C'est ce fichier-ci qui l'empêche.

Pourquoi maintenant, et pas plus tôt
------------------------------------
Sous `--dist loadfile`, « les tests suivants du même worker » était au moins l'ordre
du fichier. Sous `--dist loadgroup` (2026-09-15) la distribution se fait test par
test : qui hérite de la doublure cesse d'être prévisible, et le symptôme devient un
échec INTERMITTENT dans un fichier sans rapport.

Ce que ce garde LIT
-------------------
La STRUCTURE du script, jamais son texte : chaque littéral de chaîne qui s'analyse
comme du Python est relu par `ast`, et la question posée est « cette affectation sur
un attribut de module a-t-elle une affectation de rétablissement dans un
`finally` ? ». Un commentaire qui *décrit* le geste n'est donc pas attrapé — le
dépôt a déjà payé pour cette distinction (`test_a_guard_reads_structure_not_text`).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_TESTS = Path(__file__).resolve().parent

# `{root!r}` dans un gabarit `.format()` et `{state!r}` dans une f-string ne sont pas
# du Python analysable. On les remplace par un nom, ce qui préserve la STRUCTURE des
# instructions — seule chose que ce garde interroge.
_PLACEHOLDER = re.compile(r"\{[^{}]*\}")


def _as_python(text: str) -> ast.Module | None:
    """L'arbre du script, ou None si ce littéral n'est pas du Python."""
    try:
        return ast.parse(_PLACEHOLDER.sub("_P", text))
    except (SyntaxError, ValueError):
        return None


def _docstrings(tree: ast.AST) -> set[int]:
    """Les `id()` des littéraux qui sont des docstrings — ils ne sont pas des scripts."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def _literal_scripts(tree: ast.AST) -> list[ast.Module]:
    """Les littéraux de ce fichier qui s'analysent comme un script Python."""
    skip = _docstrings(tree)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            text = node.value
        elif isinstance(node, ast.JoinedStr):
            text = "".join(p.value if isinstance(p, ast.Constant) else "_P"
                           for p in node.values)
        else:
            continue
        if text.count("\n") < 2 or "import " not in text:
            continue
        sub = _as_python(text)
        if sub is not None:
            found.append(sub)
    return found


def _targets(node: ast.Assign) -> set[str]:
    """Les `mod.attr` affectés par cette instruction, sous la forme `(alias, attr)`."""
    out = set()
    for t in node.targets:
        if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name):
            out.add(f"{t.value.id}.{t.attr}")
    return out


def _restored_in_finally(tree: ast.AST) -> set[str]:
    """Les NOMS D'ATTRIBUT rendus dans un `finally`, où que ce `finally` vive.

    On compare sur l'attribut seul (`fernet_state`) et non sur le chemin complet
    (`router.fernet_state`), parce que l'alias diffère légitimement entre le script
    et le test qui le rend : `test_a_printed_command_is_runnable_as_printed.py` pose
    `router.fernet_state` DANS le script et le rétablit en `_router.fernet_state`
    dans le `finally` du test. Exiger le même alias ferait rougir un fichier correct.

    Le prix de ce choix, dit franchement : un rétablissement d'un attribut de MÊME
    NOM sur un autre module compterait. C'est une porte étroite — il faut un homonyme
    exact dans le même fichier — et la refermer coûterait de suivre les alias
    d'import à travers deux arbres pour un gain qu'aucune occurrence ne justifie.
    """
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for stmt in node.finalbody:
                for sub in ast.walk(stmt):
                    if isinstance(sub, ast.Assign):
                        out |= {n.split(".", 1)[1] for n in _targets(sub)}
    return out


def _module_attribute_assignments(script: ast.Module,
                                  restored: set[str] | None = None) -> set[str]:
    """Les `mod.attr` posés par ce script et rendus nulle part."""
    rendus = set(restored or ()) | _restored_in_finally(script)
    posed: set[str] = set()
    for node in ast.walk(script):
        if isinstance(node, ast.Assign):
            posed |= _targets(node)
    return {n for n in posed if n.split(".", 1)[1] not in rendus}


# Ce fichier PORTE la forme fautive, en littéral, comme éprouvette de non-vacuité.
# S'auto-balayer le ferait rougir sur sa propre démonstration — le dépôt a déjà payé
# trois fois pour cette confusion entre commettre un geste et le décrire.
_SELF = Path(__file__).name


def _offenders() -> list[tuple[str, str]]:
    bad = []
    for path in sorted(_TESTS.glob("test_*.py")):
        if path.name == _SELF:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        restored = _restored_in_finally(tree)
        for script in _literal_scripts(tree):
            for name in sorted(_module_attribute_assignments(script, restored)):
                bad.append((path.name, name))
    return bad


# Les affectations que ce garde tolère, chacune avec sa raison. Une doublure n'y entre
# pas : ce qui est listé ici ne SURVIT à rien.
_ALLOWED = {
    # `st.session_state[...]` est une souscription, pas un attribut — déjà hors du
    # prédicat. Ce qui reste et se justifie : les attributs posés sur un objet créé
    # DANS le script, qui meurt avec lui.
}


def test_no_double_posed_in_a_rendered_script_outlives_it() -> None:
    """Un script `AppTest` qui double un module le rétablit dans un `finally`."""
    bad = [(f, n) for f, n in _offenders() if n not in _ALLOWED]
    assert not bad, (
        "des doublures posées dans un script `AppTest.from_string` ne sont pas rendues.\n"
        "`AppTest` partage `sys.modules` avec le processus des tests : la doublure "
        "survit au test et tous les suivants du même worker la voient.\n"
        "Remède : `_original = mod.attr` avant, `try: ... finally: mod.attr = _original`.\n"
        + "\n".join(f"  {f} → {n}" for f, n in bad))


def test_the_guard_actually_reads_scripts() -> None:
    """Non-vacuité : le prédicat voit de vrais scripts, et il voit de vraies doublures.

    Sans ce test, une erreur de collecte rendrait le garde VERT pour toujours — la
    forme d'aveuglement la plus courante de ce dépôt.
    """
    scripts = 0
    for path in sorted(_TESTS.glob("test_*.py")):
        if path.name == _SELF:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        scripts += len(_literal_scripts(tree))
    assert scripts >= 5, f"seulement {scripts} scripts analysés — la collecte est cassée"

    # Et le prédicat DOIT attraper la forme fautive, sinon il ne garde rien.
    fautif = _as_python("import m\nm.attr = lambda: 1\nm.go()\n")
    assert fautif is not None
    assert _module_attribute_assignments(fautif) == {"m.attr"}

    corrige = _as_python(
        "import m\n_o = m.attr\nm.attr = lambda: 1\ntry:\n    m.go()\nfinally:\n    m.attr = _o\n")
    assert corrige is not None
    assert _module_attribute_assignments(corrige) == set()


def test_the_guard_is_not_fooled_by_prose() -> None:
    """Le geste décrit dans un COMMENTAIRE ou un docstring n'est pas le geste."""
    prose = _as_python(
        '"""m.attr = lambda: 1 — ceci décrit la faute, ne la commet pas."""\n'
        "import m\n# m.attr = lambda: 1\nm.go()\n")
    assert prose is not None
    assert _module_attribute_assignments(prose) == set()
