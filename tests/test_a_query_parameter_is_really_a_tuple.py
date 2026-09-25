"""`(x)` n'est pas un tuple, et `%s` sans paramètre lève — les deux en silence.

Type: Test
Uses: ast
Depends on: src/**/*.py, airflow/**/*.py
Persists in: nothing

Deux fautes d'écriture qui se ressemblent et qui produisent la même chose : une requête
qui NE TOURNE PAS, une exception attrapée plus haut, et une absence là où il y avait des
données.

  · `db.fetch_query(sql, (artist_id))` — la parenthèse ne fait pas un tuple. psycopg2
    reçoit un `int` et lève `TypeError: 'int' object does not support indexing`.
  · `db.fetch_query(sql_avec_un_%s, ())` — zéro paramètre pour un emplacement, d'où
    `IndexError: tuple index out of range`.

Mesuré le 2026-09-18 dans `pdf_exporter/_collectors.py::get_available_songs`, qui
portait **les deux** — une par branche. Résultat sur l'artiste 1 : **0 titre au lieu de
11**, sur les deux chemins. Le sélecteur de titres du document PAYANT était vide pour
tous les artistes, et la seule trace était une ligne
« PDF: get_available_songs unreadable: TypeError » dans le journal d'un conteneur.

Trouvé en lisant l'échec d'un test d'export — pas par une plainte, et aucun test ne
rougissait dessus : le `except` rend `[]`, et une liste vide est une réponse plausible.

Ce que ce garde lit
-------------------
À l'AST, tout appel `fetch_query` / `fetch_df` / `execute_query` à DEUX arguments
positionnels dont le second est :
  · une expression parenthésée qui n'est pas un `ast.Tuple` (le cas `(x)`) ;
  · un tuple/liste LITTÉRAL dont la longueur ne correspond pas au nombre de `%s` du
    SQL littéral qui le précède.

Ce qu'il ne couvre PAS
----------------------
Les paramètres construits dans une variable (`params = (...)` plus haut) : leur longueur
n'est pas connue statiquement. Et les `%s` produits par une f-string, dont le compte
dépend de l'exécution — c'est précisément la forme que `sql-fstring-identifier` surveille
sous un autre angle.

Mutation record — 2026-09-18 : en remettant `(artist_id)` puis `()` dans
`get_available_songs`, ce garde nomme chacune ; rétablis, il passe.

---
rex: []
---
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCANNED = ("src", "airflow", "tools")
_EXECUTORS = {"fetch_query", "fetch_df", "fetch_one", "fetch_all", "execute_query"}


def _sql_of(node: ast.AST) -> str | None:
    """Le SQL littéral d'un argument, ou None s'il n'est pas lisible statiquement."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return None                      # une f-string : le compte de `%s` peut varier
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        gauche, droite = _sql_of(node.left), _sql_of(node.right)
        return None if gauche is None or droite is None else gauche + droite
    return None


def _bad_calls(tree: ast.AST, rel: str) -> list[str]:
    """Executor calls whose `%s` count and parameters cannot line up."""
    out = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call)
                and getattr(n.func, "attr", "") in _EXECUTORS
                and len(n.args) == 2):
            continue
        sql, params = _sql_of(n.args[0]), n.args[1]
        if sql is None:
            continue
        trous = sql.count("%s")
        if isinstance(params, (ast.Tuple, ast.List)):
            if len(params.elts) != trous and not any(
                    isinstance(e, ast.Starred) for e in params.elts):
                out.append(f"{rel}:{n.lineno} — {trous} `%s` pour "
                           f"{len(params.elts)} paramètre(s)")
        elif trous == 1 and isinstance(params, (ast.Name, ast.Constant,
                                                ast.Attribute)):
            out.append(f"{rel}:{n.lineno} — paramètre unique NON emballé "
                       "dans un tuple : `(x)` n'est pas `(x,)`")
    return out


def _offenders() -> list[str]:
    out = []
    for base in _SCANNED:
        racine = _ROOT / base
        if not racine.is_dir():
            continue
        for path in sorted(racine.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):     # pragma: no cover
                continue
            rel = str(path.relative_to(_ROOT)).replace("\\", "/")
            out += _bad_calls(tree, rel)
    return out


def test_the_scan_sees_real_queries() -> None:
    """Anti-vacuité : sans appel lu, ce garde est vert sur rien."""
    vus = 0
    for base in _SCANNED:
        racine = _ROOT / base
        if not racine.is_dir():
            continue
        for path in racine.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):     # pragma: no cover
                continue
            vus += sum(1 for n in ast.walk(tree)
                       if isinstance(n, ast.Call)
                       and getattr(n.func, "attr", "") in _EXECUTORS)
    assert vus >= 100, (
        f"seulement {vus} appel(s) d'exécuteur SQL vus — il y en avait 300+ le "
        "2026-09-18. Le lecteur AST est cassé, ou les exécuteurs ont changé de nom.")


def test_no_query_passes_the_wrong_number_of_parameters() -> None:
    fautifs = _offenders()
    assert not fautifs, (
        f"{len(fautifs)} requête(s) ne peuvent pas s'exécuter.\n"
        "Elles lèvent `TypeError` ou `IndexError`, un `except` les attrape, et "
        "l'appelant reçoit une liste vide qui se lit comme « il n'y a rien ».\n"
        "Mesuré le 2026-09-18 : `get_available_songs` rendait 0 titre au lieu de 11 "
        "dans le PDF, sur ses DEUX branches, sans qu'aucun test ne rougisse.\n  "
        + "\n  ".join(fautifs[:15]))


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity on FABRICATED calls: `(x)` for one `%s` (the 2026-09-18 shape that
    made `get_available_songs` return 0 titles), a count mismatch, and the corrections."""
    src = ("db.fetch_query('SELECT * FROM t WHERE a = %s', (artist_id))\n"
           "db.fetch_query('SELECT * FROM t WHERE a = %s AND b = %s', (artist_id,))\n"
           "db.fetch_query('SELECT * FROM t WHERE a = %s', (artist_id,))\n"
           "db.fetch_query('SELECT * FROM t WHERE a = %s AND b = %s', (a, b))\n")
    bad = _bad_calls(ast.parse(src), "fake.py")
    assert [b.split(" — ")[0] for b in bad] == ["fake.py:1", "fake.py:2"], bad
