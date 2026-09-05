#!/usr/bin/env python3
"""Les signatures de classes qui inspectent du code PYTHON, lues sur l'arbre.

Un `grep` sur du source Python est satisfait — ou déclenché — par un commentaire,
une docstring, une chaîne de log. Six signatures du catalogue portaient ce défaut,
dont une `deterministic` bloquante en CI. Ce script les remplace : une fonction par
classe, chacune lisant `ast`, et un `--class <id>` qui sort ≠ 0 sur un hit.

Usage :
    python3 .claude/scripts/audit_python_signatures.py --class db-connection-per-show
    python3 .claude/scripts/audit_python_signatures.py --all

---
rex:
  - date: 2026-09-04
    issue: "Six `signature.cmd` du catalogue cherchaient une sous-chaîne dans du
      source Python. Un commentaire pouvait supprimer un hit (`view-session-adoption`,
      `csv-formula-injection`, `db-connection-per-show`) ou en fabriquer un
      (`guide-single-os-shortcut`, `deterministic` donc bloquante : documenter le
      correctif en commentaire cassait la CI)."
    fix: "Un auditeur unique, une fonction par classe, lecture AST. Les lignes
      `signature:` du catalogue pointent dessus."
    severity: crit
---
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_VIEWS = _ROOT / "src" / "dashboard" / "views"


def _tree(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return None


def _calls(tree: ast.AST, name: str) -> list[ast.Call]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and (getattr(n.func, "attr", None) == name
                 or getattr(n.func, "id", None) == name)]


# ── db-connection-per-show ──────────────────────────────────────────────────
def db_connection_per_show() -> list[str]:
    """Plus d'UN `get_db_connection()` réellement appelé dans un fichier de vue.

    Le compteur textuel du catalogue (`grep -c "get_db_connection("`) est le MÊME
    que celui de `tests/test_view_connection_budget.py`, dont le docstring documente
    qu'il a été pris en défaut sur ses propres commentaires le 2026-08-22. Le second
    site n'avait jamais été corrigé.
    """
    out = []
    for path in sorted(_VIEWS.rglob("*.py")):
        tree = _tree(path)
        if tree is None:
            continue
        n = len(_calls(tree, "get_db_connection"))
        if n > 1:
            out.append(f"{path.relative_to(_ROOT)}: {n} appels")
    return out


# ── view-session-adoption ───────────────────────────────────────────────────
def view_session_adoption() -> list[str]:
    """Une vue qui ouvre la connexion à la main sans passer par `view_session`.

    Le `grep -q view_session` du catalogue excluait un fichier dès qu'un COMMENTAIRE
    nommait `view_session` — « # TODO migrer vers view_session » suffisait à le
    retirer de la dette qu'il incarne.
    """
    out = []
    for path in sorted(_VIEWS.rglob("*.py")):
        tree = _tree(path)
        if tree is None:
            continue
        if not _calls(tree, "get_db_connection"):
            continue
        uses = _calls(tree, "view_session") or [
            n for n in ast.walk(tree)
            if isinstance(n, ast.withitem) and "view_session" in ast.dump(n.context_expr)
        ]
        if not uses:
            out.append(str(path.relative_to(_ROOT)))
    return out


# ── csv-formula-injection ───────────────────────────────────────────────────
def csv_formula_injection() -> list[str]:
    """Un `to_csv`/`to_excel` dont la valeur n'est pas passée par `defang_formulas`.

    Le grep excluait TOUTE ligne contenant `#` — donc un vrai export non défangé
    suivi d'un commentaire inoffensif. Sur une classe CWE-1236.
    """
    out = []
    for path in sorted((_ROOT / "src" / "dashboard").rglob("*.py")):
        tree = _tree(path)
        if tree is None:
            continue
        defanged = bool(_calls(tree, "defang_formulas"))
        for call in _calls(tree, "to_csv") + _calls(tree, "to_excel"):
            recv = ast.dump(call.func)
            if defanged or "defang" in recv:
                continue
            out.append(f"{path.relative_to(_ROOT)}:{call.lineno}")
    return out


# ── guide-single-os-shortcut ────────────────────────────────────────────────
_OS_SHORTCUT = re.compile(r"Ctrl\+[A-Z]|F12")


def guide_single_os_shortcut() -> list[str]:
    """Un raccourci clavier figé dans une CHAÎNE rendue à l'artiste.

    Polarité inverse des trois au-dessus : le grep échouait dès que le motif
    apparaissait n'importe où — y compris dans le commentaire documentant son
    retrait. `deterministic`, donc la CI cassait en faux positif, et la seule façon
    de la garder verte était d'arrêter de documenter le correctif.
    """
    targets = [
        _ROOT / "src" / "dashboard" / "content",
        _ROOT / "src" / "dashboard" / "views" / "credentials",
        _ROOT / "src" / "dashboard" / "utils" / "i18n_catalog" / "credentials.py",
    ]
    out = []
    for base in targets:
        files = sorted(base.rglob("*.py")) if base.is_dir() else [base]
        for path in files:
            tree = _tree(path)
            if tree is None:
                continue
            # Les docstrings ne sont pas rendues à l'artiste : ce sont des
            # constantes dans l'arbre, mais pas du TEXTE d'interface. Les compter
            # ramènerait le faux positif qu'on ferme.
            docstrings: set[int] = set()
            for holder in ast.walk(tree):
                if not isinstance(holder, (ast.Module, ast.FunctionDef,
                                           ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                body = getattr(holder, "body", None)
                if not body or not isinstance(body[0], ast.Expr):
                    continue
                first = body[0].value
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    docstrings.add(id(first))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                        and id(node) not in docstrings
                        and _OS_SHORTCUT.search(node.value)):
                    out.append(f"{path.relative_to(_ROOT)}:{node.lineno}")
    return out


# ── api-partial-date-into-date-column ───────────────────────────────────────
def api_partial_date_into_date_column() -> list[str]:
    """`release_date` lu brut de l'API Spotify, sans normalisation.

    L'API rend `"2019"` ou `"2019-03"` selon la précision ; une colonne DATE les
    refuse. Le grep cherchait la ligne fautive EXACTE — donc une citation de cette
    ligne en commentaire (la documentation du bug) cassait la CI.
    """
    path = _ROOT / "src" / "collectors" / "spotify_api.py"
    tree = _tree(path)
    if tree is None:
        return []
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        if getattr(node.targets[0], "id", None) != "release_date":
            continue
        dumped = ast.dump(node.value)
        # Normalisé = le résultat passe par un helper, pas par un indexage direct.
        if "Subscript" in dumped and "Call" not in dumped:
            out.append(f"{path.relative_to(_ROOT)}:{node.lineno}")
    return out


CHECKS = {
    "db-connection-per-show": db_connection_per_show,
    "view-session-adoption": view_session_adoption,
    "csv-formula-injection": csv_formula_injection,
    "guide-single-os-shortcut": guide_single_os_shortcut,
    "api-partial-date-into-date-column": api_partial_date_into_date_column,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--class", dest="klass", choices=sorted(CHECKS))
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if not args.klass and not args.all:
        ap.error("passe --class <id> ou --all")

    names = sorted(CHECKS) if args.all else [args.klass]
    total = 0
    for name in names:
        hits = CHECKS[name]()
        for h in hits:
            print(f"{name}: {h}")
        total += len(hits)
    if total:
        print(f"\n{total} occurrence(s).", file=sys.stderr)
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
