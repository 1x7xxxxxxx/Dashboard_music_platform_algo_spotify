"""Un total ne se calcule pas en pandas sur une table de fait brute.

Type: Test
Uses: ast
Depends on: src/dashboard/**/*.py, tests/test_the_metrics_layer_only_grows.py
Persists in: nothing

Why this exists
---------------
`tests/test_the_metrics_layer_only_grows.py` tient à zéro les `SUM(` écrits en SQL
hors de la couche or. Il ne peut rien voir d'un total calculé **après** la
requête :

    df = db.fetch_df("SELECT campaign_name, spend, … FROM meta_insights_performance …")
    tot_spend = df['spend'].sum()          # ← aucun `SUM(` dans le SQL

Mesuré le 2026-09-12, c'est exactement ce que faisait la tuile « Dépenses » de la
page Meta Ads : **6 165,65 €** affichés là où la couche or en comptait
**3 087,82** — la table portait deux générations de lignes, quotidiennes et cumul
à vie, et pandas les additionnait toutes. Un facteur deux, sur un chiffre que
l'artiste lit pour décider de son budget, invisible à tout garde SQL du dépôt.

Le second site avait la même forme sans le même symptôme : les quatre tuiles de
la page SoundCloud sommaient un `DISTINCT ON (track_id)` **sans locataire** —
juste, aujourd'hui, parce qu'aucun titre n'est partagé.

Ce que le prédicat refuse, exactement
-------------------------------------
Une frame issue d'un `fetch_df` dont le SQL (a) lit une table de FAIT et (b) ne
l'agrège pas, puis réduite par `.sum()`, `.mean()`, `.median()`, `.cumsum()` ou
`.prod()`.

Trois choses NE sont pas refusées, et c'est volontaire :

  * une frame issue d'une **vue or** — c'est le but ; la règle est déjà descendue
    et sommer les lignes rendues est la bonne façon de lire un grain ;
  * un `len(df)` ou un `.max()` sur une date — un décompte et un dernier relevé
    ne sont pas des métriques à centraliser ;
  * un total en pandas sur une requête qui agrège DÉJÀ en SQL — le grain est posé,
    le reste est de la présentation.

La liste des tables de fait est celle du cliquet des agrégats, importée et non
recopiée : deux listes divergent, une seule ne peut pas.

Mutation record — 2026-09-12 : avec `meta_ads_overview.query_perf` remis sur
`meta_insights_performance` sans `GROUP BY`, ce garde nomme les cinq `.sum()` de
la page ; avec la page SoundCloud remise sur son `DISTINCT ON` brut, il nomme les
quatre siennes. Vu rouge sur les deux défauts qu'il existe pour empêcher.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SCANNED = _ROOT / "src" / "dashboard"

_AGG_SQL = re.compile(r"\b(SUM|AVG|COUNT|MIN|MAX)\s*\(", re.I)
_FROMJOIN = re.compile(r"\b(?:FROM|JOIN)\s+(?:public\.)?([a-zA-Z_][a-zA-Z0-9_]*)", re.I)

# Les réductions qui produisent un NOMBRE AFFIRMÉ. `max` et `min` en sont absents
# à dessein : sur une date ils répondent « dernier relevé », qui n'est pas une
# métrique — et les y mettre aurait rendu ce garde bruyant là où il a raison.
_REDUCERS = {"sum", "mean", "median", "cumsum", "prod"}

_READERS = {"fetch_df"}


def _fact_tables() -> frozenset[str]:
    """La liste du cliquet des agrégats, IMPORTÉE. Deux listes divergent.

    Par `sys.path` et non par `spec_from_file_location` : la première version
    enregistrait le module sous un nom inventé dans `sys.modules` et ne l'en
    retirait jamais. `test_no_test_stubs_an_installed_package.py` l'a refusée —
    un nom laissé dans `sys.modules` casse les imports du reste de la session, et
    ce n'est visible QUE lorsque les deux fichiers tournent ensemble. Seul de son
    côté, mon test était vert.
    """
    sys.path.insert(0, str(_ROOT / "tests"))
    import test_the_metrics_layer_only_grows as ratchet
    return frozenset(t for tables in ratchet._FACTS.values() for t in tables)


def _sql_of(node: ast.AST, scope: dict[str, ast.AST] | None = None,
            depth: int = 0) -> str | None:
    """Le texte SQL d'une expression, en suivant les variables.

    ⚠️ La PREMIÈRE version de ce lecteur ne suivait pas les variables, et elle est
    restée VERTE sur le défaut qu'elle existait pour attraper : `meta_ads_overview`
    écrit `query_perf = (…)` puis `db.fetch_df(query_perf, params)`, donc l'argument
    est un `Name`. Mutation faite, garde vert — la cinquième fois que ce dépôt
    mesure « la portée du garde est le défaut », et la première où je l'ai vue sur
    un garde que je venais d'écrire pour ça.
    """
    if depth > 3:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "{}"
                       for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _sql_of(node.left, scope, depth + 1) or ""
        right = _sql_of(node.right, scope, depth + 1) or ""
        return (left + right) or None
    if isinstance(node, ast.Name) and scope and node.id in scope:
        return _sql_of(scope[node.id], scope, depth + 1)
    if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "format":
        return _sql_of(node.func.value, scope, depth + 1)
    return None


def _root_name(node: ast.AST) -> str | None:
    while isinstance(node, (ast.Subscript, ast.Attribute)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _sites(facts: frozenset[str]) -> list[str]:
    out: list[str] = []
    for path in sorted(_SCANNED.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = path.relative_to(_ROOT).as_posix()
        # Les constantes de module : `_QUERY_X = """…"""` juste au-dessus.
        module_scope: dict[str, ast.AST] = {
            t.id: stmt.value
            for stmt in tree.body if isinstance(stmt, ast.Assign)
            for t in stmt.targets if isinstance(t, ast.Name)
        }
        for fn in (n for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
            scope = dict(module_scope)
            for stmt in ast.walk(fn):
                if isinstance(stmt, ast.Assign):
                    for t in stmt.targets:
                        if isinstance(t, ast.Name):
                            scope[t.id] = stmt.value
            raw: dict[str, tuple[list[str], int]] = {}
            for node in ast.walk(fn):
                if not (isinstance(node, ast.Assign)
                        and isinstance(node.value, ast.Call)
                        and getattr(node.value.func, "attr", "") in _READERS
                        and node.value.args):
                    continue
                sql = _sql_of(node.value.args[0], scope)
                if not sql or _AGG_SQL.search(sql):
                    continue                      # déjà agrégé en SQL : le grain est posé
                tables = sorted({t for t in _FROMJOIN.findall(sql) if t in facts})
                if not tables:
                    continue                      # lit une vue or, ou rien de factuel
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        raw[target.id] = (tables, node.lineno)
            for node in ast.walk(fn):
                if not (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr in _REDUCERS):
                    continue
                name = _root_name(node.func.value)
                if name in raw:
                    tables, read_at = raw[name]
                    out.append(
                        f"{rel}:{node.lineno} — `{name}.{node.func.attr}()` réduit "
                        f"les lignes brutes de {', '.join(tables)} lues ligne "
                        f"{read_at}, sans que le SQL les agrège.")
    return sorted(set(out))


def test_no_total_is_summed_in_pandas_over_a_raw_fact_table() -> None:
    facts = _fact_tables()
    assert facts, "la liste des tables de fait est vide — le garde ne garde rien"
    offenders = _sites(facts)
    assert not offenders, (
        "Un total est calculé en pandas sur des lignes de fait brutes. Aucun garde\n"
        "SQL ne peut le voir : il n'y a pas de `SUM(` dans la requête.\n\n"
        "C'est ainsi que la tuile « Dépenses » de la page Meta Ads a affiché\n"
        "6 165,65 € pour 3 087,82 € réels — un facteur deux sur le chiffre qui sert\n"
        "à décider d'un budget.\n\n"
        "Remède : lire une vue or, ou agréger en SQL. Les deux rendent le total\n"
        "visible à un garde.\n\n" + "\n".join(offenders))


def test_the_scan_reaches_real_reducers() -> None:
    """Un prédicat sans site est vert et ne garde rien — la 5ᵉ fois dans ce dépôt.

    On ne vérifie pas qu'il y a des OFFENSEURS (il n'y en a plus), mais que le
    balayage voit bien des `fetch_df` et des réductions pandas. Le jour où
    `fetch_df` est renommé, ce test le dit au lieu de passer au vert à vide.
    """
    readers = reducers = 0
    for path in _SCANNED.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in _READERS:
                    readers += 1
                elif node.func.attr in _REDUCERS:
                    reducers += 1
    assert readers >= 50, f"seulement {readers} appels à fetch_df vus — le lecteur est cassé"
    assert reducers >= 30, f"seulement {reducers} réductions pandas vues — idem"
