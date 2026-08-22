#!/usr/bin/env python3
"""Report how many charts each dashboard view puts in the viewer's eye span.

Type: Utility
Uses: nothing (stdlib — ast)
Triggers: `make chart-budget`
Persists in: nothing

The criterion, sourced (R29, 2026-08-22)
────────────────────────────────────────
This tool shipped on 2026-08-21 as a plain count per view, and said so honestly:
"nobody here has a SOURCE for 'N charts per view is too many'", because the
`ux-frontend` corpus was empty. It is not empty any more (R17), and what it says
changes the measurement rather than supplying the missing number.

  Stephen Few, *Information Dashboard Design*, p.27:
    "A dashboard fits on a single computer screen. The information must fit on a
     single screen, entirely available within the viewer's eye span so it can all be
     seen at once, at a glance."

  Same book, p.39, §3.1 *Exceeding the Boundaries of a Single Screen*:
    "a dashboard should confine its display to a single screen, with no need for
     scrolling or switching between multiple screens"

  Same book, p.81:
    "Limited to a single screen to keep all the data within eye span, dashboard real
     estate is extremely valuable: you can't afford to waste an inch."

So the unit is not the view and not the file: it is **what is visible at once**.
That has two consequences the old count got wrong in opposite directions.

  * A chart inside a collapsed container is NOT in the eye span. Charts moved into
    `secondary_analyses()` — the pattern already applied to instagram, soundcloud and
    spotify — are one click away by design, and counting them made a view that had
    correctly applied the pattern score exactly like one that had not.
  * A chart in a non-default tab is not in the eye span either, but Few explicitly
    counts tab-switching as exceeding the boundary ("or switching between multiple
    screens"), so it is reported separately rather than forgiven. `trigger_algo` is
    an analytical workspace, not a monitoring dashboard in Few's sense; the number is
    for a human to weigh, which is why nothing here fails.

There is still NO pass/fail threshold, and adding one would be inventing a number the
source does not give. What the source gives is the right thing to count.

Parsing is AST, not regex: "is this call inside a `with st.expander(...)`" is a
structural question, and a regex answers it by accident at best.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
VIEWS = ROOT / "src/dashboard/views"

_CHART_CALLS = {
    "plotly_chart", "altair_chart", "bar_chart", "line_chart", "area_chart",
    "pyplot", "map",
}
# Context managers that hide their body behind a click.
_COLLAPSING = {"expander", "secondary_analyses", "popover", "dialog"}
# `st.tabs(...)` returns handles used as `with tab2:`; only the first is open on load.
_TAB_FACTORY = "tabs"


class _Counter(ast.NodeVisitor):
    """Charts split by how much work it takes the viewer to see them."""

    def __init__(self) -> None:
        self.at_a_glance = 0
        self.behind_a_click = 0
        self.in_another_tab = 0
        self._collapsed = 0
        self._tab_names: list[str] = []
        self._tab_depth = 0        # inside a `with <non-first tab>:`

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _call_name(node: ast.AST) -> str | None:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            return node.func.attr
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return node.func.id
        return None

    def visit_Assign(self, node: ast.Assign) -> None:
        # tab1, tab2, ... = st.tabs([...])  → remember every handle but the first,
        # because only the first is rendered open.
        if self._call_name(node.value) == _TAB_FACTORY and node.targets:
            target = node.targets[0]
            if isinstance(target, ast.Tuple):
                self._tab_names = [
                    e.id for e in target.elts[1:] if isinstance(e, ast.Name)
                ]
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        collapsing = tabbed = False
        for item in node.items:
            name = self._call_name(item.context_expr)
            if name in _COLLAPSING:
                collapsing = True
            ctx = item.context_expr
            if isinstance(ctx, ast.Name) and ctx.id in self._tab_names:
                tabbed = True
        self._collapsed += collapsing
        self._tab_depth += tabbed
        self.generic_visit(node)
        self._collapsed -= collapsing
        self._tab_depth -= tabbed

    def visit_Call(self, node: ast.Call) -> None:
        if (isinstance(node.func, ast.Attribute)
                and node.func.attr in _CHART_CALLS
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "st"):
            if self._collapsed:
                self.behind_a_click += 1
            elif self._tab_depth:
                self.in_another_tab += 1
            else:
                self.at_a_glance += 1
        self.generic_visit(node)


def _count_file(path: Path) -> dict[str, int] | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        print(f"  (skipped {path.relative_to(ROOT)} — does not parse)", file=sys.stderr)
        return None
    counter = _Counter()
    counter.visit(tree)
    return {"at_a_glance": counter.at_a_glance,
            "behind_a_click": counter.behind_a_click,
            "in_another_tab": counter.in_another_tab}


def counts() -> dict[str, dict[str, int]]:
    """{view: {at_a_glance, behind_a_click, in_another_tab, screens, worst_screen}}.

    `at_a_glance` sums the whole view; `worst_screen` is the largest single MODULE.

    Both are reported because neither alone is honest for a tabbed view. A package
    view (`trigger_algo/`) renders each tab from its own module, and the `with tab2:`
    block calls `_tab_algos.show()` — so the tab detection below, which is
    syntactic, stops at the call and every chart in that module reads as top-level.
    The sum then over-counts the eye span sevenfold, and per-module under-counts a
    tab that legitimately holds several charts. `screens` says how many modules the
    view is spread over, which is the number that tells you which column to read.
    """
    out: dict[str, dict[str, int]] = {}
    for entry in sorted(VIEWS.iterdir()):
        if entry.is_file() and entry.suffix == ".py":
            files, name = [entry], entry.stem
        elif entry.is_dir():
            files, name = sorted(entry.rglob("*.py")), entry.name
        else:
            continue
        totals = {"at_a_glance": 0, "behind_a_click": 0, "in_another_tab": 0,
                  "screens": 0, "worst_screen": 0}
        for f in files:
            per_file = _count_file(f)
            if per_file is None:
                continue
            for key, value in per_file.items():
                totals[key] += value
            if sum(per_file.values()):
                totals["screens"] += 1
                totals["worst_screen"] = max(totals["worst_screen"],
                                             per_file["at_a_glance"])
        if totals["at_a_glance"] or totals["behind_a_click"] or totals["in_another_tab"]:
            out[name] = totals
    return out


def main() -> int:
    data = counts()
    if not data:
        print("no view renders a chart — check the path", file=sys.stderr)
        return 1

    glance = sorted(v["worst_screen"] if v["screens"] > 1 else v["at_a_glance"]
                    for v in data.values())
    median = glance[len(glance) // 2]
    # NOT sum(v.values()): `screens` and `worst_screen` are metadata, and
    # including them turned 83 charts into 171 for one run of this tool.
    total = sum(v["at_a_glance"] + v["behind_a_click"] + v["in_another_tab"]
                for v in data.values())
    print(f"{len(data)} view(s) carry charts · {total} total · "
          f"median {median} in the eye span (Few, IDD p.27)")
    print()
    print(f"  {'glance':>6} {'worst':>6} {'click':>6} {'tab':>4} {'mods':>5}  view")
    for name, v in sorted(data.items(), key=lambda kv: -kv[1]["worst_screen"]):
        # Judge a multi-module view on its worst single screen, a single-module one
        # on its total — they are the same number when `mods` is 1.
        judged = v["worst_screen"] if v["screens"] > 1 else v["at_a_glance"]
        mark = "  ← above twice the median, at a glance" if judged > 2 * median else ""
        print(f"  {v['at_a_glance']:>6} {v['worst_screen']:>6} "
              f"{v['behind_a_click']:>6} {v['in_another_tab']:>4} "
              f"{v['screens']:>5}  {name}{mark}")
    print()
    print("  glance = charts rendered on arrival, summed over the whole view")
    print("  worst  = the largest single MODULE — for a tabbed view this is the")
    print("           screen the viewer actually faces; read it when mods > 1")
    print("  click  = inside secondary_analyses()/expander — one click away, not in the")
    print("           eye span, and deliberately so")
    print("  tab    = in a non-default tab. Few p.39 counts switching screens as")
    print("           exceeding the boundary too, so these are shown, not forgiven.")
    print("  mods   = modules the view renders from. Tab detection is syntactic, so a")
    print("           `with tab2: _tab_x.show()` hides its charts from the tab column;")
    print("           that is why `worst` exists and why `glance` over-counts here.")
    print()
    print("Report only. The source gives no threshold — it gives the unit of measure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
