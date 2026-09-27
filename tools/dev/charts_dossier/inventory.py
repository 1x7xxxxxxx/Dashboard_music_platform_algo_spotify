"""The static list of every figure site, with its data source and layer — from gold-coverage.

Type: Utility
Uses: tools/dev/gold_coverage.py (load_python, build_call_index, Slicer, collect_surfaces,
      collect_pdf, layer_of, scan_sql, sql_wrappers)
Triggers: tools/dev/charts_dossier/main.py, tests/test_the_charts_dossier_covers_every_figure.py
Persists in: nothing

R203 (2026-09-26). The capture sees what a DEFAULT render draws; this sees every code site that
CAN draw. The dossier needs both: a site with no image is listed with its reason, never
dropped — the same rule as the capture's « not rendered ».
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


_MEASURE_KW = ("x", "y", "values", "names", "z", "r", "theta")
_RENDER_CALLS = ("plotly_chart", "pyplot", "altair_chart", "bar_chart", "line_chart",
                 "area_chart")


def _key_of(node) -> str:
    """A measure argument as a stable token: 'col' for 'col' or df['col'], else its code."""
    import ast
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
        return str(node.slice.value)
    return ast.unparse(node)


def measure_of(tree, line: int) -> tuple:
    """What the figure rendered at `line` PLOTS — the `y=`/`values=`/`z=`/`r=` arguments of
    the figure built before it (R207, 2026-09-27). Structural, never the prose: the chart's
    variable is traced back to its last assignment in the same function, and every
    constructor or `add_trace` call on it up to the render line contributes.

    A duplicate is two figures of one page that read the same SOURCES and plot the same
    MEASURE; sources alone matched 24 sites that plot different things (code-critic)."""
    import ast
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.lineno <= line <= (n.end_lineno or n.lineno)), None)
    if fn is None:
        return ()
    render = next((n for n in ast.walk(fn) if isinstance(n, ast.Call) and n.lineno == line
                   and getattr(n.func, "attr", getattr(n.func, "id", "")) in _RENDER_CALLS
                   and n.args), None)
    if render is None:
        return ()
    arg = render.args[0]
    if isinstance(arg, ast.Call):
        name = ast.unparse(arg.func)
        if name.split(".")[0] in ("px", "go"):
            # A generic constructor built inline: its arguments are the measure.
            return tuple(sorted({_key_of(kw.value) for kw in arg.keywords
                                 if kw.arg in _MEASURE_KW}))
        # A figure built by a dedicated helper: the helper IS its measure — two calls of
        # the same helper on one page are the duplicate, two different helpers are not.
        return ("call:" + name,)
    if not isinstance(arg, ast.Name):
        return ()
    var = arg.id
    starts = [n.lineno for n in ast.walk(fn) if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == var for t in n.targets)
              and n.lineno <= line]
    if not starts:
        return ()
    start = max(starts)
    found = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and start <= n.lineno <= line:
            for kw in n.keywords:
                if kw.arg in _MEASURE_KW:
                    found.add(_key_of(kw.value))
    return tuple(sorted(found))


def sites() -> list[dict]:
    """[{site, key, kind ('figure'|'pdf'), fn, visible, layer, sources, measure}] — one per site.

    `key` is STABLE: `file::function#n`, the n-th figure of that function in source order.
    `site` (`file:line`) moves at every edit above it; keyed by it, the owner's comments
    detached from their chart after the first merge (2026-09-26, R205/R216)."""
    sys.path.insert(0, str(ROOT / "tools" / "dev"))
    import gold_coverage as gc
    gold, known = gc.scan_sql()
    files = gc.load_python()
    calls = gc.build_call_index(files)
    slicer = gc.Slicer(files, calls, gold, known, gc.sql_wrappers(files))
    import collections
    out, nth = [], collections.Counter()
    surfaces = [s for s in gc.collect_surfaces(files, slicer) + gc.collect_pdf(files, slicer)
                if s.kind in ("figure", "pdf")]
    import ast
    trees: dict = {}
    for s in sorted(surfaces, key=lambda s: (s.rel, s.line)):
        nth[(s.rel, s.fn)] += 1
        if s.kind == "figure" and s.rel not in trees:
            trees[s.rel] = ast.parse((ROOT / s.rel).read_text(encoding="utf-8"))
        out.append({"site": f"{s.rel}:{s.line}", "key": f"{s.rel}::{s.fn}#{nth[(s.rel, s.fn)]}",
                    "kind": s.kind, "fn": s.fn, "visible": s.visible,
                    "layer": gc.layer_of(s.sl),
                    "sources": sorted(name for _, name in s.sl.sources),
                    "measure": (list(measure_of(trees[s.rel], s.line))
                                if s.kind == "figure" else [])})
    return out
