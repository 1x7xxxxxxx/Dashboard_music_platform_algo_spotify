"""`secondary_analyses()` was written for a note, and applied nowhere it was aimed.

R51. `src/dashboard/utils/ui.py` carries the function AND the reason for it — an
artist's 2026-08-12 remark, quoted in the file: too many charts on one screen. It was
used on four incidental views and on NONE of the five dense ones it was written for,
`trigger_algo` foremost (≈35 figures on one page).

This is `feedback_correct_code_nothing_reaches` in its purest form: code that is
correct, tested, documented — and applied nowhere it was meant to be. A render test
cannot see it, because every one of those charts renders perfectly.

The guard names the five views the brick names, and checks the pattern is present in
each. It asserts adoption, never a chart count: rebalancing a view is normal, and a
count would make ordinary work fail.
"""
from __future__ import annotations

import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
VIEWS = REPO / "src/dashboard/views"

# The five named in R51, with the figure counts measured when it was written.
_DENSE = {
    "trigger_algo": "≈35 figures (15 charts + up to 17 gauges)",
    "data_wrapped": "9 figures",
    "meta_creatives": "8 figures",
    "meta_ads_overview": "8 figures",
    "revenue_forecast": "6 figures",
}


def _files(view: str) -> list[pathlib.Path]:
    path = VIEWS / view
    return sorted(path.rglob("*.py")) if path.is_dir() else [VIEWS / f"{view}.py"]


def _calls_the_pattern(view: str) -> bool:
    """Is `secondary_analyses` actually CALLED here — read from the AST.

    Never a text search. The first version of this assertion searched the source, and
    the mutation that removed the real `with secondary_analyses(...)` left it green:
    the explanatory comment written beside the fix contains the name. A guard that
    passes on its own documentation guards the documentation.
    """
    import ast

    for f in _files(view):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                fn = node.func
                name = getattr(fn, "id", None) or getattr(fn, "attr", None)
                if name == "secondary_analyses":
                    return True
    return False


@pytest.mark.parametrize("view, density", sorted(_DENSE.items()))
def test_each_dense_view_collapses_its_secondary_charts(view, density):
    assert _calls_the_pattern(view), (
        f"{view} ({density}) shows everything at once. `secondary_analyses()` exists "
        "for exactly this and is one import away — nothing needs designing.")


def test_the_pattern_itself_is_still_there():
    """Non-vacuity: the parametrised assertions above all hinge on this name.

    ⚠️ Lu par l'AST depuis le 2026-09-21, et c'est une CORRECTION de portée, pas un
    assouplissement. La forme d'avant cherchait la chaîne `"expanded=False"` dans le
    fichier. Elle est devenue rouge le jour où `secondary_analyses` a gagné un
    paramètre `expanded: bool = False` — la valeur par défaut était toujours
    `False`, donc la propriété gardée était toujours vraie, et le garde parlait de
    l'ORTHOGRAPHE. Symétriquement il serait resté VERT sur
    `expanded=True` si le mot `expanded=False` avait survécu dans un commentaire :
    c'est la classe `a-textual-guard-that-matches-its-own-prose`, prise quatre fois
    dans ce dépôt.

    La question est : quelle valeur un appelant qui ne dit rien obtient-il ? Le
    défaut du paramètre la donne, et rien d'autre.
    """
    import ast

    src = (REPO / "src/dashboard/utils/ui.py").read_text(encoding="utf-8")
    fn = next((n for n in ast.walk(ast.parse(src))
               if isinstance(n, ast.FunctionDef) and n.name == "secondary_analyses"),
              None)
    assert fn is not None, "`secondary_analyses` a disparu — le motif n'existe plus"

    args = fn.args
    named = [a.arg for a in args.args] + [a.arg for a in args.kwonlyargs]
    assert "expanded" in named, (
        "`secondary_analyses` n'expose plus `expanded` : son état d'ouverture n'est "
        f"plus une décision lisible ici. Paramètres vus : {named}")

    if "expanded" in [a.arg for a in args.kwonlyargs]:
        i = [a.arg for a in args.kwonlyargs].index("expanded")
        default = args.kw_defaults[i]
    else:
        i = [a.arg for a in args.args].index("expanded")
        offset = len(args.args) - len(args.defaults)
        default = args.defaults[i - offset] if i >= offset else None

    assert isinstance(default, ast.Constant) and default.value is False, (
        "le dépliant est OUVERT par défaut : un appelant qui ne dit rien ne replie "
        "plus rien, et c'est tout le point du premier écran. Ouvrir reste possible "
        "site par site (`secondary_analyses(expanded=True)`), et ce choix-là se lit "
        "dans la vue qui le prend.")
