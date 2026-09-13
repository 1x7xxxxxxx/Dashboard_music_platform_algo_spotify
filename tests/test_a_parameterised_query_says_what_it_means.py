"""Deux façons pour une requête paramétrée de trahir, trouvées le même jour.

Type: Test
Uses: pytest, ast
Depends on: src/
Persists in: nothing

Les deux classes gardées ici
----------------------------
Elles n'ont rien à voir l'une avec l'autre au fond, et tout en surface : ce sont les
deux seules choses qu'un littéral SQL peut dire sans que personne les lise, parce que
le lecteur regarde les clauses et pas la ponctuation.

**1. `a-percent-sign-in-a-parameterised-query`** — `psycopg2` interpole le signe
pour cent dans TOUTE la chaîne, **commentaires SQL compris**. Un seul, écrit dans la
prose d'un `--`, fait échouer la requête entière sur `IndexError: tuple index out of
range` — un message qui parle de PARAMÈTRES alors que le compte des paramètres est
juste. Mesuré le 2026-09-13 : 35 emplacements, 35 valeurs, et le signe de trop était
dans un commentaire expliquant un taux. Écrit **deux fois de suite**, la seconde dans
le paragraphe qui mettait en garde contre la première.

**2. `an-empty-group-wins-a-desc-ranking`** — dans PostgreSQL, `ORDER BY x DESC`
place les `NULL` **en PREMIER**. Un classement « le meilleur » dont l'expression peut
valoir `NULL` — typiquement un ratio construit sur `NULLIF(dénominateur, 0)` —
sélectionne donc le groupe VIDE avant tous les autres. Vérifié en base le 2026-09-13 :
une campagne à zéro visite sortait devant une campagne à 46 pour cent. La porte est un
`HAVING` qui écarte les groupes vides, ou un `NULLS LAST` explicite.

Pourquoi par l'AST, et pourquoi les docstrings sont exclues
------------------------------------------------------------
Une recherche textuelle rougirait sur CE fichier, qui décrit les deux défauts, et sur
tout commentaire expliquant un correctif. Ce dépôt s'est fait prendre ainsi trois fois
le 2026-09-04 : un garde qui bloque sur la prose de son propre fix apprend que le rouge
est du bruit. Les littéraux sont donc lus par `ast`, et les **docstrings en sont
retirées** — ce sont aussi des `ast.Constant`.

Portée : `src/`, les seuls littéraux qui atteignent une vraie connexion.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

_SQL = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|WITH)\b", re.I)
# La frontière entre deux CTE d'un même littéral. Sans elle, le `HAVING` d'une CTE
# exempte toutes ses voisines : mesuré le 2026-09-13, le `HAVING` de `best_cpr`
# rendait le garde aveugle au retrait de celui de `hypeddit_release`, dans la même
# requête. Un littéral n'est pas une unité de raisonnement SQL.
_CTE_BOUNDARY = re.compile(r"\)\s*,\s*\w+\s+AS\s*\(", re.I)


def _sql_literals() -> list[tuple[Path, int, str]]:
    """Tous les littéraux de `src/`, docstrings exclues."""
    out: list[tuple[Path, int, str]] = []
    for path in sorted((REPO / "src").rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        docstrings = {
            id(node.body[0].value.value)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef))
            and node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)}
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant)
                    and isinstance(node.value, str)):
                continue
            if id(node.value) in docstrings:
                continue
            out.append((path, node.lineno, node.value))
    return out


def test_no_stray_percent_sign_in_a_parameterised_query() -> None:
    """Classe `a-percent-sign-in-a-parameterised-query`.

    Un littéral qui porte `%s` est destiné à `psycopg2`. Tout autre signe pour cent
    qui n'est pas doublé y est une bombe — y compris dans un commentaire `--`.
    """
    hits = []
    for path, line, text in _sql_literals():
        if "%s" not in text or not _SQL.search(text):
            continue
        if "%" in re.sub(r"%[s%]", "", text):
            hits.append(f"{path.relative_to(REPO)}:{line}")

    assert not hits, (
        "signe pour cent isolé dans un littéral SQL paramétré : " + ", ".join(hits)
        + "\n`psycopg2` interpole ce signe dans toute la chaîne, COMMENTAIRES SQL "
        "COMPRIS. La requête échouera sur `IndexError: tuple index out of range`, "
        "un message qui accuse les paramètres alors que leur compte est juste. "
        "Le doubler (`%%`), ou écrire « pour cent » en toutes lettres.")


def test_a_desc_ranking_cannot_be_won_by_an_empty_group() -> None:
    """Classe `an-empty-group-wins-a-desc-ranking`.

    Le prédicat est volontairement étroit : il ne se déclenche que sur un classement
    `ORDER BY … DESC … LIMIT` dont l'expression est construite sur `NULLIF`, donc
    nullable par construction. C'est le seul cas où l'on sait, sans exécuter, qu'un
    `NULL` peut remonter en tête.
    """
    hits = []
    for path, line, text in _sql_literals():
        query = re.sub(r"--[^\n]*", "", text)
        if not re.search(r"\bNULLIF\b", query, re.I):
            continue
        for chunk in _CTE_BOUNDARY.split(query):
            if not re.search(r"\bNULLIF\b", chunk, re.I):
                continue
            if not re.search(r"\bORDER\s+BY\b[^)]*?\bDESC\b", chunk, re.I):
                continue
            if not re.search(r"\bLIMIT\b", chunk, re.I):
                continue
            if re.search(r"\bNULLS\s+LAST\b", chunk, re.I):
                continue
            if re.search(r"\bHAVING\b", chunk, re.I):
                continue
            hits.append(f"{path.relative_to(REPO)}:{line}")

    assert not hits, (
        "classement décroissant sur une expression nullable, sans porte : "
        + ", ".join(sorted(set(hits)))
        + "\nPostgreSQL place les NULL EN PREMIER sur un `ORDER BY … DESC` : le "
        "groupe VIDE est donc choisi avant tous les autres, et la surface affiche "
        "« — » alors qu'un vrai chiffre existe. Ajouter `HAVING` pour écarter les "
        "groupes vides, ou `NULLS LAST` pour le dire explicitement.")


def test_the_two_predicates_are_not_vacuous() -> None:
    """Un garde dont le prédicat ne voit aucun site ne garde rien.

    Les deux tests ci-dessus sont des assertions NÉGATIVES : elles passent au vert
    sur zéro littéral, donc sur un `_sql_literals()` cassé. Ce test-ci vérifie que le
    balayage atteint réellement le corpus qu'il prétend lire.
    """
    literals = _sql_literals()
    sql = [t for _p, _l, t in literals if "%s" in t and _SQL.search(t)]
    assert len(sql) >= 20, (
        f"seulement {len(sql)} littéral(aux) SQL paramétré(s) trouvé(s) dans src/ : "
        "le balayage ne lit plus le corpus, et les deux gardes ci-dessus sont verts "
        "sur du vide.")
    nullif = [t for _p, _l, t in literals if re.search(r"\bNULLIF\b", t, re.I)]
    assert nullif, (
        "aucun littéral n'utilise `NULLIF` : le second garde n'a plus de site, "
        "il faut vérifier que la portée est toujours la bonne.")
