"""
Guard — no line of the dashboard runs outside the exception boundary.

Type: Sub
Uses: ast, pathlib
Triggers: pytest
Depends on: src/dashboard/app.py
Persists in: nothing

Error class: boundary-narrower-than-the-surface.

Mesuré end-to-end dans un vrai navigateur le 2026-08-23. Une frontière existait déjà —
autour de `_render_page` **seulement**, soit 10 des 90 lignes de `main()`. Les 80 autres
portaient huit appels de vue, dont les surfaces **non authentifiées** : page vie privée,
onboarding, barres latérales.

Avec `showErrorDetails=full` — la valeur EFFECTIVE en production ce jour-là, faute d'avoir
été réglée — une exception levée sur ces chemins rendait dans la page :

    RuntimeError: HttpError 403 when requesting
    https://www.googleapis.com/youtube/v3/channels?part=statistics&key=AIza…
    Traceback:  File ".../app.py", line …

soit la clé API YouTube en clair (elle voyage dans la query string, donc dans le message
de l'exception), les chemins de fichiers et le code. Vérifié dans les deux sens : avec
`none`, la même page ne rend qu'un message générique et ni la clé ni la traceback
n'apparaissent, pas même dans le HTML.

Ce test ne remplace pas le réglage, il le rend SECOND. Un réglage unique dont l'absence
est le défaut ne peut pas être la seule ligne de défense.
"""

import ast
from pathlib import Path

_APP = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "app.py"


def _main() -> ast.FunctionDef:
    tree = ast.parse(_APP.read_text(encoding="utf-8"))
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main")


def test_main_is_nothing_but_the_boundary():
    """`main()` ne contient qu'un docstring, des imports, et le `try`."""
    body = _main().body
    allowed = (ast.Expr, ast.Import, ast.ImportFrom, ast.Try)
    stray = [type(n).__name__ + f"@L{n.lineno}" for n in body
             if not isinstance(n, allowed)]
    assert not stray, (
        f"{stray} s'exécute dans main() en dehors du try. Toute ligne hors frontière "
        f"peut rendre sa traceback au visiteur si `showErrorDetails` régresse."
    )
    tries = [n for n in body if isinstance(n, ast.Try)]
    assert len(tries) == 1, f"attendu exactement un try dans main(), trouvé {len(tries)}"


def test_no_view_is_called_outside_the_boundary():
    """Aucun `show*()` ne s'exécute hors du try — c'est la forme exacte du défaut."""
    main = _main()
    tries = [n for n in ast.walk(main) if isinstance(n, ast.Try)]
    covered = set()
    for t in tries:
        covered |= set(range(t.lineno, (t.end_lineno or t.lineno) + 1))

    outside = []
    for n in ast.walk(main):
        if isinstance(n, ast.Call) and n.lineno not in covered:
            name = getattr(n.func, "id", "") or getattr(n.func, "attr", "")
            if name.startswith("show") or name == "_main_body":
                outside.append(f"{name}@L{n.lineno}")
    assert not outside, (
        f"{outside} : appel de vue hors frontière. Les surfaces NON AUTHENTIFIÉES "
        f"(vie privée, onboarding, barres latérales) étaient précisément celles qui "
        f"restaient dehors avant le 2026-08-23."
    )


def test_control_flow_still_propagates():
    """`st.stop()` / `st.rerun()` doivent traverser : sinon toute navigation casse.

    C'est la contrainte qui rend la frontière difficile à écrire correctement, et la
    raison pour laquelle on ne peut pas se contenter d'un `except Exception: pass`.
    """
    main = _main()
    src = ast.get_source_segment(_APP.read_text(encoding="utf-8"), main) or ""
    assert "is_control_flow" in src, (
        "la frontière doit re-lever les signaux de contrôle Streamlit"
    )
    tree = ast.parse(src)
    reraises = [n for n in ast.walk(tree) if isinstance(n, ast.Raise) and n.exc is None]
    assert reraises, "aucun `raise` nu : les signaux de contrôle seraient avalés"
