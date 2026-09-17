"""Une liste de noms écrite à la main, dans un garde, DIT ce qu'elle laisse dehors.

Type: Test
Uses: ast
Depends on: tests/, .claude/scripts/, src/dashboard/views/, airflow/dags/
Persists in: nothing

Trouvé le 2026-09-17 en balayant les frères de `un-garde-qui-ne-garde-pas`, dont
**cinq instances** avaient été trouvées la même soirée avec toujours la même cause :
un garde énumère une population au lieu de la DÉRIVER, la population grandit, et le
garde reste vert sur ce qu'il ne regarde plus.

Le balayage : parmi les **80** listes de noms écrites à la main dans les gardes du
dépôt, chercher celles dont ≥ 70 % des entrées appartiennent à une population que le
dépôt CONNAÎT (les vues de `src/dashboard/views/`, les DAG de `airflow/dags/`, les
tables d'`init_db.sql`). Quatre en sont sorties, toutes sur les vues :

    KNOWN_PREMIUM_PAGES    6 / 46   test_plan_gating.py
    _VIEWS                11 / 46   test_a_view_says_something_or_says_why.py
    _NON_ANALYTICS        11 / 46   test_pdf_coverage.py
    TENANT_VIEWS          22 / 46   test_stray_session_reads_nothing.py

⚠️ **Un sous-ensemble n'est PAS un défaut** : les pages premium SONT un sous-ensemble,
et les vues non-analytiques aussi. Le défaut est le sous-ensemble qui se croit — ou se
laisse lire — exhaustif. C'est pourquoi ce garde n'exige pas la dérivation : il exige
que la liste DISE combien elle couvre, pour qu'un lecteur ne prenne jamais 11 pour 46.

⚠️ Le balayage a d'ailleurs corrigé DEUX de mes propres affirmations du même jour :
j'avais écrit « sur les 36 vues » pour un garde qui en regarde **11**, et pour un
balayage AST qui en parcourt **41**. Aucun des deux chiffres n'avait été mesuré.

Mutation record — 2026-09-17, deux mutations, deux vues ROUGES :
  1. retirer la note de couverture d'une des quatre listes → rouge, liste nommée.
  2. `_DERIVABLE` vidé                                      → rouge (anti-vacuité).

---
rex: []
---
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

# Les quatre listes mesurées, avec le fichier qui les porte. Ce n'est PAS une liste
# gelée d'exemptions : c'est la population à laquelle ce garde s'applique, et elle
# grandit par `test_no_new_derivable_list_escapes_this_guard`.
_DERIVABLE = {
    "KNOWN_PREMIUM_PAGES": "tests/test_plan_gating.py",
    "_VIEWS": "tests/test_a_view_says_something_or_says_why.py",
    "_NON_ANALYTICS": "tests/test_pdf_coverage.py",
    "TENANT_VIEWS": "tests/test_stray_session_reads_nothing.py",
}

# La marque qu'une liste doit porter : un chiffre, ou le mot qui dit qu'elle est
# partielle. « 11 des 46 », « sous-ensemble », « pas exhaustive », « /46 ».
_COVERAGE_MARKS = ("sur les", "sur 4", "/4", "sous-ensemble", "pas exhaust",
                   "non exhaust", "subset", "not exhaustive", "of the 4", "des 4")


def _views() -> set[str]:
    d = _ROOT / "src" / "dashboard" / "views"
    noms = {p.stem for p in d.glob("*.py") if not p.stem.startswith("_")}
    noms |= {p.name for p in d.iterdir()
             if p.is_dir() and not p.name.startswith(("_", "."))}
    return noms


def test_the_population_is_readable() -> None:
    """Anti-vacuité : sans vues, tout ce fichier passe."""
    assert len(_views()) >= 30, (
        f"seulement {len(_views())} vues trouvées — le garde ne voit plus sa population")


def test_each_derivable_list_says_what_it_leaves_out() -> None:
    """Une liste partielle porte son chiffre, à portée de l'œil qui la lit."""
    muettes = []
    for nom, rel in sorted(_DERIVABLE.items()):
        chemin = _ROOT / rel
        if not chemin.exists():
            muettes.append(f"{rel} a disparu — retirer `{nom}` d'ici DANS LE MÊME COMMIT")
            continue
        texte = chemin.read_text(encoding="utf-8")
        # la note peut vivre dans la docstring du module ou près de la liste
        if not any(m in texte for m in _COVERAGE_MARKS):
            muettes.append(f"{rel} :: `{nom}`")
    assert not muettes, (
        "des listes de noms écrites à la main n'annoncent PAS ce qu'elles laissent "
        "dehors :\n  " + "\n  ".join(muettes)
        + f"\n\nLe produit porte {len(_views())} vues. Une liste de 11 lue comme une "
          "liste de 46 fait conclure « c'est couvert » sur 35 vues que personne ne "
          "regarde — c'est ce qui s'est produit deux fois le 2026-09-17, dans le "
          "catalogue lui-même.\n"
          "Remède : une phrase qui donne le compte (« 11 des 46 vues : … »), ou "
          "dériver la liste de `src/dashboard/views/`.")


def test_no_new_derivable_list_escapes_this_guard() -> None:
    """Et la population du garde grandit toute seule quand une liste neuve apparaît."""
    vues = _views()
    neuves = []
    for p in sorted((_ROOT / "tests").glob("test_*.py")):
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:                      # pragma: no cover
            continue
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            cible = node.targets[0] if isinstance(node, ast.Assign) else node.target
            nom = getattr(cible, "id", "")
            if not nom.isupper() or nom in _DERIVABLE:
                continue
            val = node.value
            if isinstance(val, ast.Call) and getattr(val.func, "id", "") in (
                    "frozenset", "set", "tuple", "list"):
                val = val.args[0] if val.args else None
            if not isinstance(val, (ast.Set, ast.List, ast.Tuple)):
                continue
            vals = {e.value for e in getattr(val, "elts", [])
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)}
            if len(vals) < 3:
                continue
            inter = vals & vues
            if len(inter) >= 3 and len(inter) / len(vals) >= 0.7:
                neuves.append(f"{p.relative_to(_ROOT)} :: `{nom}` "
                              f"({len(inter)}/{len(vues)} vues)")
    assert not neuves, (
        "des listes de NOMS DE VUES écrites à la main ne sont pas déclarées ici :\n  "
        + "\n  ".join(neuves)
        + "\n\nLes ajouter à `_DERIVABLE` — et vérifier qu'elles annoncent leur "
          "couverture. Une liste de vues qui grandit toute seule n'existe pas : c'est "
          "le lecteur qui doit savoir ce qu'elle ne regarde pas.")
