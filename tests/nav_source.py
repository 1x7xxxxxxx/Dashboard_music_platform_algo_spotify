"""Où vit la DÉCLARATION du menu — un seul endroit, pour les gardes qui la lisent.

Type: Utility
Uses: ast, src/dashboard/utils/nav_sections.py
Depends on: src/dashboard/utils/nav_sections.py
Persists in: nothing

Pourquoi ce module existe
-------------------------
Neuf gardes lisaient `_NAV_SECTIONS` dans `src/dashboard/app.py`, chacun avec sa
propre façon de l'y trouver — un `ast.parse` ici, un `read_text()` et une recherche
de sous-chaîne là. Le 2026-09-12 la constante a déménagé dans
`utils/nav_sections.py` (le cliquet de longueur d'`app.py` l'exigeait), et **les
neuf sont devenus rouges d'un coup**.

Ce n'est pas la mauvaise nouvelle : chacun a rougi sur sa propre assertion de
NON-VACUITÉ — « seulement 0 libellés lus », « this guard is now blind », « la
lecture du menu a cassé » — donc aucun n'est passé vert en ne mesurant plus rien.
C'est exactement ce que ces assertions existent pour faire, et c'est la première
fois qu'elles le prouvent toutes ensemble.

La mauvaise nouvelle est le NOMBRE : neuf copies d'une même question — « où est le
menu ? ». Le prochain déplacement coûterait neuf éditions, et la tentation à la
neuvième est d'assouplir plutôt que de suivre. Une seule copie ici : le prochain
déplacement en coûte une.

Ce module ne juge rien. Il dit seulement où lire et rend la déclaration.
"""
from __future__ import annotations

import ast
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Le FICHIER qui porte la déclaration, et le NOM qu'elle y prend. Les deux ont déjà
# changé ensemble une fois ; ils changeront ensemble la prochaine.
NAV_PATH = _ROOT / "src" / "dashboard" / "utils" / "nav_sections.py"
NAV_NAME = "NAV_SECTIONS"


def nav_text() -> str:
    """Le SOURCE de la déclaration — pour les gardes qui lisent les commentaires."""
    return NAV_PATH.read_text(encoding="utf-8")


def nav_node() -> ast.AST:
    """Le nœud AST de la liste, jamais une recherche de sous-chaîne.

    Lever plutôt que rendre `None` : un garde qui reçoit `None` ici et l'ignore est
    un garde vert qui ne mesure rien — la panne que ce dépôt paie le plus souvent.
    """
    tree = ast.parse(nav_text(), filename=str(NAV_PATH))
    for n in ast.walk(tree):
        if isinstance(n, ast.AnnAssign) and getattr(n.target, "id", "") == NAV_NAME:
            return n.value
        if isinstance(n, ast.Assign) and any(
                getattr(t, "id", "") == NAV_NAME for t in n.targets):
            return n.value
    raise AssertionError(
        f"`{NAV_NAME}` introuvable dans {NAV_PATH.relative_to(_ROOT)} — la "
        f"déclaration du menu a encore déménagé. Mets `NAV_PATH`/`NAV_NAME` à jour "
        f"ICI, et les neuf gardes qui en dépendent suivront.")


def nav_sections() -> list:
    """`[(id, en-tête, [(libellé, clé), …]), …]` — la déclaration, évaluée.

    `ast.literal_eval` et pas un `import` : la lire comme une donnée garantit qu'on
    juge le fichier, pas ce qu'un autre module aurait pu y substituer.
    """
    return ast.literal_eval(nav_node())


def menu_pages() -> set:
    """Toutes les clés de page atteignables depuis le menu."""
    return {key for _sid, _hdr, items in nav_sections() for _lbl, key in items}


def menu_labels() -> set:
    """Tous les libellés affichés dans le menu."""
    return {lbl for _sid, _hdr, items in nav_sections() for lbl, _key in items}


def menu_entries() -> list:
    """`[(libellé, clé), …]`, dans l'ordre du menu."""
    return [(lbl, key) for _sid, _hdr, items in nav_sections() for lbl, key in items]
