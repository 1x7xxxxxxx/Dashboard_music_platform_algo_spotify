"""Guard: an artist has exactly ONE place to drop a CSV, and it is reachable.

Type: Utility
Uses: ast, pathlib
Triggers: pytest
Persists in: nothing

Error class `two-widgets-for-one-gesture`.

Measured 2026-09-06. `st.file_uploader` was instantiated by `upload_csv.show()` AND —
through the same `render_uploader` — by the `📂 Mes fichiers` tab of the Credentials
page. Two widgets, therefore two Streamlit session states: a file dropped on one was
invisible on the other, which reads as a loss rather than as two pages. The
`upload_csv` page had left the menu on 2026-09-04 but stayed routed, and
`platform_value.CSV` kept sending artists to it from the setup picker — so the
duplicate was not hypothetical, it was the recommended route.

What is asserted here is the artist's experience, not a file layout: how many
uploader widgets can a non-admin reach, and does the destination every CSV platform
advertises actually contain one.

Admin surfaces are out of scope: `admin.py` restores backups and seeds fixtures, a
different gesture with a different audience.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.dashboard.content.platform_value import CSV, PLATFORM_VALUES
from src.dashboard.views.credentials.router import CSV_TAB_KEY, platform_destination


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


_VIEWS = _repo_root() / "src" / "dashboard" / "views"
_ADMIN_ONLY = {"admin.py"}


def _uploader_sites(path: Path) -> list[str]:
    """`fichier:ligne` of every `st.file_uploader(...)` CALL — by AST, not by grep.

    A docstring or a comment naming the widget must not count: three guards in this
    repo have already gone green on their own prose.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        f"{path.name}:{n.lineno}"
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "file_uploader"
    ]


def test_exactly_one_uploader_widget_exists_outside_admin():
    """Two widgets = two session states = a file that seems to vanish."""
    sites: list[str] = []
    for path in sorted(_VIEWS.rglob("*.py")):
        if path.name in _ADMIN_ONLY:
            continue
        sites += _uploader_sites(path)
    assert len(sites) == 1, (
        f"{len(sites)} zones de dépôt hors admin : {sites}. Un fichier déposé dans "
        "l'une n'existe pas pour l'autre — Streamlit garde un état par widget. "
        "Rendre `upload_csv.render_uploader` depuis un second endroit ne partage "
        "pas l'état : il faut y MENER, pas le refabriquer."
    )


def test_every_csv_platform_points_at_the_tab_that_holds_the_uploader():
    """The destination advertised must be the one place, not a page that redirects."""
    csv_keys = [pv.key for pv in PLATFORM_VALUES if pv.where == CSV]
    assert csv_keys, "aucune plateforme CSV : ce test ne prouverait rien"
    for key in csv_keys:
        assert platform_destination(key) == f"tab:{CSV_TAB_KEY}", (
            f"{key} → {platform_destination(key)}, pas l'onglet de dépôt")


def test_the_one_uploader_sits_in_a_module_the_router_never_renders_as_a_page():
    """The uploader is a COMPONENT, not a page — and the difference is measurable.

    Written after getting this wrong. `upload_csv.show()` was rewritten to point at
    the tab, and the pointer was correct, and nothing could ever display it:
    `app.py` routes `?page=upload_csv` to `views.credentials`, and imports
    `views.upload_csv` **nowhere**. A page nothing routes to is not a second place —
    it is dead code that looks like one, which is worse, because a reader counts it.

    So the assertion is about REACHABILITY, not about the text of a redirect.
    """
    src = (_VIEWS / "upload_csv.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    assert not [n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "show"], (
        "upload_csv définit de nouveau `show()`. Aucune route ne l'importe "
        "(`app.py` envoie `?page=upload_csv` vers `views.credentials`), donc elle "
        "serait morte à la seconde où elle est écrite — et un test de rendu qui "
        "l'appelle directement la ferait passer pour vivante.")

    # Par AST et non par `"views.upload_csv" not in app_src` : la seconde forme est
    # satisfaite — ou brisée — par un COMMENTAIRE. Le commentaire d'app.py qui
    # explique justement cette route la mentionne, donc la version textuelle serait
    # rouge sur sa propre documentation (`guard-matches-its-own-comment`).
    app_tree = ast.parse((_VIEWS.parent / "app.py").read_text(encoding="utf-8"))
    imported = {n.module for n in ast.walk(app_tree)
                if isinstance(n, ast.ImportFrom) and n.module}
    assert not {m for m in imported if m.endswith("upload_csv")}, (
        "app.py importe de nouveau views.upload_csv : ce module est le composant "
        "de dépôt, pas une page.")


def test_the_retired_route_still_lands_on_the_tab_that_holds_the_uploader():
    """`?page=upload_csv` is bookmarked and linked; it must reach the drop tab."""
    app_src = (_VIEWS.parent / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(app_src)
    branch = next(
        (n for n in ast.walk(tree)
         if isinstance(n, ast.Compare) and getattr(n.left, "id", "") == "page"
         and n.comparators and isinstance(n.comparators[0], ast.Constant)
         and n.comparators[0].value == "upload_csv"), None)
    assert branch is not None, (
        "la route `upload_csv` a disparu d'app.py — six pointeurs la visent, "
        "elle deviendrait un cul-de-sac")
    # La branche `elif` qui la porte doit rendre la page Credentials.
    parent = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.If) and n.test is branch)
    rendered = {imp.module for imp in ast.walk(parent)
                if isinstance(imp, ast.ImportFrom) and imp.module}
    assert "views.credentials" in rendered, (
        f"`?page=upload_csv` rend {sorted(rendered)} et non `views.credentials` — "
        "l'artiste qui suit un ancien lien n'atterrit pas sur la zone de dépôt.")


@pytest.mark.parametrize("fn", ["render_uploader"])
def test_the_uploader_is_still_callable_from_the_tab(fn: str):
    """The tab renders it by calling this; a rename would silently empty the tab."""
    import src.dashboard.views.upload_csv as mod
    assert callable(getattr(mod, fn, None)), (
        f"upload_csv.{fn} a disparu — l'onglet « 📂 Mes fichiers » l'appelle")
