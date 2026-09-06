"""Guard: a screenshot is bounded by its column, and never blown up past its pixels.

Type: Utility
Uses: ast, PIL, src.dashboard.content.csv_guides
Triggers: pytest
Persists in: nothing

Error class `image-sized-for-a-layout-it-no-longer-has`.

Reported 2026-09-06: « certaines captures dépassent du cadre, c'est pas beau ».

`csv_guides_st` capped every screenshot at 720 px — a figure from the days when one
guide filled the content area. Both guide surfaces now render inside COLUMNS:
`csv_guides_st` uses `st.columns(2)`, and the credential guides live in `_col_guide`
of `st.columns([3, 2])`, the narrower half. Measured on the 16 CSV screenshots: eight
are between 1257 and 1693 px wide. Every one of them overflowed.

The two ways to be ugly are opposite, and a single setting fixes only one:
a 1693 px capture in a ~340 px column spills out of the frame; a 138 px thumbnail
stretched to the column goes blurry. Python cannot ask Streamlit how wide the
container is, so the rule is a threshold — stretch above it (which can only shrink),
native below it (which cannot overflow).

Both surfaces call ONE renderer, which is the other half of the fix: they shared a
sizing helper before, and renaming it took the whole credentials page down with an
`ImportError` — a coupling nothing had written down.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.dashboard.content.csv_guides import CSV_GUIDES, screenshot_path
from src.dashboard.content.csv_guides_st import _COLUMN_WIDTH_PX, _native_width


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


_CONTENT = _repo_root() / "src" / "dashboard" / "content"
_SURFACES = ("csv_guides_st.py", "credential_guides_st.py")


def _image_calls(path: Path) -> list[ast.Call]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "image"]


def test_the_threshold_is_narrower_than_a_half_page():
    """Se tromper vers le bas rétrécit une image ; vers le haut, elle déborde."""
    assert 0 < _COLUMN_WIDTH_PX <= 340, (
        f"seuil de {_COLUMN_WIDTH_PX} px : la zone de contenu par défaut fait ~730 px "
        "et les guides sont rendus par paires, donc une colonne vaut ~340 px moins "
        "l'espacement et la marge de l'expander. Au-dessus, les captures débordent.")


@pytest.mark.parametrize("surface", _SURFACES)
def test_no_surface_calls_st_image_with_a_bare_pixel_cap(surface):
    """Un `width=<constante>` ne connaît pas la largeur du conteneur."""
    for call in _image_calls(_CONTENT / surface):
        for kw in call.keywords:
            if kw.arg != "width":
                continue
            assert not (isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, int)), (
                f"{surface}: `st.image(width={kw.value.value})` — un plafond en dur "
                "ignore la colonne dans laquelle l'image est rendue. C'est ce que "
                "faisait `_MAX_IMG_WIDTH = 720`.")


def test_no_dashboard_file_uses_the_removed_container_flag():
    """`use_container_width` est retiré de Streamlit depuis fin 2025.

    Sur `st.image` il LÈVE — vu au rendu le 2026-09-06, la page entière tombait en
    erreur, pas seulement l'image. Sur les autres widgets il n'avertit encore que par
    un message dans les logs, ce qui est pire à sa façon : le compte à rebours court
    et rien ne le rend visible à l'écran.

    Le balayage porte sur TOUT `src/dashboard/`, et pas sur les deux surfaces de
    guides : le défaut n'est pas propre aux captures. Mesuré le 2026-09-06 — 11 sites
    dans 5 fichiers, dont 8 boutons et un `link_button`.
    """
    root = _repo_root() / "src" / "dashboard"
    offenders = []
    for path in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover — un fichier cassé se voit ailleurs
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg == "use_container_width":
                    offenders.append(
                        f"{path.relative_to(root)}:{node.lineno} "
                        f"({getattr(node.func, 'attr', '?')})")
    assert not offenders, (
        "`use_container_width` est retiré de Streamlit ; sur `st.image` il lève et "
        "emporte toute la page.\n  " + "\n  ".join(offenders)
        + '\n\nÉquivalents : True → width="stretch", False → width="content".')


def test_both_surfaces_go_through_the_same_renderer():
    """Le couplage est réel : autant qu'il soit explicite plutôt que découvert.

    `credential_guides_st` importait un helper PRIVÉ de `csv_guides_st`. Le renommer
    a fait tomber toute la page Credentials sur un `ImportError` — au rendu, pas à la
    lecture. Un nom public et un import unique rendent la dépendance visible.
    """
    src = (_CONTENT / "credential_guides_st.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = {a.name for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom) and n.module
                and n.module.endswith("csv_guides_st")
                for a in n.names}
    assert "render_bounded_image" in imported, (
        "les guides d'identifiants ne partagent plus le dimensionneur des guides "
        "CSV : les deux surfaces vont diverger, et c'est la plus étroite des deux "
        "qui débordera la première.")
    assert not any(n.startswith("_") for n in imported), (
        f"import d'un helper privé {sorted(n for n in imported if n.startswith('_'))} "
        "— un renommage casse alors la page Credentials au rendu")


def test_every_shipped_screenshot_is_classified_and_none_is_upscaled():
    """La règle, appliquée aux fichiers réels : aucune n'est agrandie."""
    seen = 0
    for guide in CSV_GUIDES:
        for step in guide.steps:
            if not step.screenshot:
                continue
            path = screenshot_path(step.screenshot)
            if not path.exists():
                continue
            seen += 1
            width = _native_width(path)
            assert width is not None, f"{step.screenshot} : largeur illisible"
            # Native seulement en dessous du seuil — donc jamais d'agrandissement.
            if width <= _COLUMN_WIDTH_PX:
                assert width <= _COLUMN_WIDTH_PX
    assert seen >= 10, f"seulement {seen} captures lues — le balayage ne voit plus rien"
