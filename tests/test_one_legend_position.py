"""One legend position for the whole app: top right, on the chart (R536).

Type: Test
Uses: src.dashboard.utils.charts (apply_defaults, LEGEND_POSITION)

Owner, 2026-10-12: « les légendes en haut à droite, sur le graphique, cohérent dans toute
l'app ». On that day 31 local `legend=dict(...)` placements put it below, above, centred,
left — one per author. The door (`charts.apply_defaults`) now owns the place, and:

1. a figure that arrives with its own placement leaves the door with the door's;
2. no module under `src/` other than charts.py writes a legend POSITION — read from the
   syntax tree (a `legend=dict(...)` keyword or a `legend_x=`-style keyword), never from
   the text, so this docstring and comments do not trip it.

Not covered: an attribute assignment (`fig.layout.legend.y = …`) — none exists today, and
rule 1 overrides it anyway for every chart that goes through the door.
"""
from __future__ import annotations

import ast
import pathlib

import plotly.graph_objects as go

from src.dashboard.utils import charts

_POS = {"orientation", "x", "y", "xanchor", "yanchor"}


def _two_traces(**layout) -> go.Figure:
    fig = go.Figure([go.Scatter(y=[1, 2], name="a"), go.Scatter(y=[2, 1], name="b")])
    fig.update_layout(**layout)
    return fig


def test_a_local_placement_leaves_the_door_top_right():
    fig = charts.apply_defaults(_two_traces(legend=dict(orientation="h", y=-0.3, x=0,
                                                        groupclick="toggleitem")))
    leg = fig.layout.legend
    assert (leg.x, leg.y, leg.xanchor, leg.yanchor) == (1, 1, "right", "top")
    assert leg.groupclick == "toggleitem", "the door must keep what is not a position"


def test_a_figure_with_no_legend_gets_none():
    fig = charts.apply_defaults(_two_traces(showlegend=False))
    assert fig.layout.showlegend is False


def _position_writes(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg and kw.arg.startswith("legend_") and kw.arg[7:] in _POS:
                out.append(f"{path}:{kw.lineno} {kw.arg}=")
            if (kw.arg == "legend" and isinstance(kw.value, ast.Call)
                    and getattr(kw.value.func, "id", "") == "dict"):
                keys = {k.arg for k in kw.value.keywords} & _POS
                if keys:
                    out.append(f"{path}:{kw.lineno} legend=dict({', '.join(sorted(keys))})")
            if kw.arg == "legend" and isinstance(kw.value, ast.Dict):
                keys = {k.value for k in kw.value.keys if isinstance(k, ast.Constant)} & _POS
                if keys:
                    out.append(f"{path}:{kw.lineno} legend={{{', '.join(sorted(keys))}}}")
    return out


def test_no_module_places_its_own_legend():
    offenders = [hit for p in sorted(pathlib.Path("src").rglob("*.py"))
                 if p.name != "charts.py" for hit in _position_writes(p)]
    assert not offenders, ("a legend position written outside the door — the door "
                           "(charts.LEGEND_POSITION) overrides it, delete it:\n"
                           + "\n".join(offenders))


def test_the_scanner_sees_each_spelling(tmp_path):
    f = tmp_path / "v.py"
    f.write_text("fig.update_layout(legend=dict(orientation='h', y=-0.2))\n"
                 "fig.update_layout(legend={'x': 0})\n"
                 "fig.update_layout(legend_y=1.1)\n"
                 "fig.update_layout(legend=dict(groupclick='toggleitem'))\n"
                 "# legend=dict(orientation='h')\n", encoding="utf-8")
    assert len(_position_writes(f)) == 3
