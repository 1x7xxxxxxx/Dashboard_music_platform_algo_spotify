"""R478 — a comparison of releases opens on the two LATEST, through ONE picker.

Type: Test
Uses: ast, src/dashboard/utils/release_picker.py, src/dashboard/views/**

Owner, 2026-10-09 (W7, W11) : « méthode de comparaison différente des autres vues →
mêmes filtres cohérents dans toute l'app », « d'office les deux dernières sorties ».
Before R478 the rule lived at three call sites written three ways : a multiselect
`default=titles[:2]` (SoundCloud), another `default=labels[:2]` (Spotify for Artists),
and two side-by-side selectboxes « Sortie » / « Comparer avec » (Apple Music).

The PROPERTY held here : a widget that picks titles by slicing the head of a list is
the « n latest » rule ; it must be `release_picker`, so the rule has one definition.
A slice is read from the AST — `default=x[:n]` — never from a variable name.
"""
from __future__ import annotations

import ast
import pathlib

from src.dashboard.utils.release_picker import LATEST_RELEASES, default_releases

ROOT = pathlib.Path(__file__).resolve().parents[1]
VIEWS = ROOT / "src" / "dashboard" / "views"

# Head-slices that are NOT a release comparison — each with its reason.
EXEMPT: dict[str, str] = {}


def _is_head_slice(v: ast.AST) -> bool:
    return (isinstance(v, ast.Subscript) and isinstance(v.slice, ast.Slice)
            and v.slice.lower is None and v.slice.upper is not None)


def _hand_rolled_latest(source: str) -> list[int]:
    """Lines of widgets whose `default=` is a head slice `x[:n]` — written inline or
    through a name bound to one (`default = labels[:2]` then `default=default`, the
    Spotify for Artists form). Pure."""
    tree = ast.parse(source)
    sliced = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign)
              and _is_head_slice(n.value) for t in n.targets if isinstance(t, ast.Name)}
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "attr", "")
                in {"multiselect", "pills", "segmented_control"}):
            continue
        for kw in node.keywords:
            v = kw.value
            if kw.arg == "default" and (_is_head_slice(v) or (
                    isinstance(v, ast.Name) and v.id in sliced)):
                out.append(node.lineno)
    return out


def test_no_view_writes_the_latest_releases_rule_by_hand():
    hits = {}
    for p in sorted(VIEWS.rglob("*.py")):
        rel = str(p.relative_to(VIEWS))
        lines = _hand_rolled_latest(p.read_text(encoding="utf-8"))
        if lines and rel not in EXEMPT:
            hits[rel] = lines
    assert not hits, (
        f"« les n dernières sorties » réécrit à la main : {hits} — "
        "utilise `release_picker` (src/dashboard/utils/release_picker.py)")


def test_the_picker_opens_on_the_two_latest():
    assert LATEST_RELEASES == 2
    assert default_releases(["new", "prev", "old"]) == ["new", "prev"]
    assert default_releases(["only"]) == ["only"]


def test_the_detector_sees_the_defect_it_is_written_for():
    """Non-vacuité : sur le code EXACT du défaut, le détecteur doit mordre."""
    defect = "st.multiselect('Titres', titles, default=titles[:2], key='k')"
    assert _hand_rolled_latest(defect) == [1], "le défaut n'est pas vu"
    fixed = "release_picker('Titres', titles, key='k')"
    assert not _hand_rolled_latest(fixed), "le correctif ferait rougir le garde"
    assert _hand_rolled_latest("d = labels[:2]\nst.multiselect('S', labels, default=d)") == [2], (
        "la forme par variable intermédiaire (Spotify for Artists) n'est pas vue")
    assert not _hand_rolled_latest("st.multiselect('X', xs, default=xs)"), (
        "« tout sélectionné » n'est pas la règle des dernières sorties")


def _launch_selectboxes(source: str) -> list[int]:
    """Lines of selectboxes keyed `apple_launch*` — the two-list comparison. Pure, AST."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "selectbox":
            for kw in node.keywords:
                if (kw.arg == "key" and isinstance(kw.value, ast.Constant)
                        and str(kw.value.value).startswith("apple_launch")):
                    out.append(node.lineno)
    return out


def test_the_apple_comparison_is_no_longer_two_selectboxes():
    """The Apple form had no slice at all — two selectboxes, read by their key."""
    src = (VIEWS / "apple_music.py").read_text(encoding="utf-8")
    assert not _launch_selectboxes(src), "la comparaison Apple a repris ses deux listes"
    defect = ("a = c.selectbox('S', xs, key='apple_launch_a')\n"
              "b = c.selectbox('C', xs, key='apple_launch_b')")
    assert _launch_selectboxes(defect) == [1, 2], "le défaut n'est pas vu"
    assert not _launch_selectboxes("# key='apple_launch_b'\nrelease_picker('S', xs, key='k')")
