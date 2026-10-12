"""R544 — the three gates of the Accueil are 0-100 gauges, red → green, with a cursor.

Type: Test
Uses: src/dashboard/views/home_tiles.py (gate_gauge, _gate_sub, render_tiles)
Depends on: plotly
Persists in: nothing

Owner, 2026-10-12 (voice note): « pour les pourcentages de trigger … une jauge entre 0 à
100, rouge, vert, et où en est le curseur. Et essaye d'intégrer dans cette jauge-là le
montant qui resterait à intégrer au meilleur CPR ».

Mutation record (2026-10-12): the threshold (cursor) value pinned to 50 → red; the
bands reversed (green → red) → red; the `sub` annotation dropped → red; `render_tiles`
back on `stat_box` for the gates (no `_render_gate` call) → red.
"""
from __future__ import annotations

import ast
from pathlib import Path

from src.dashboard.views import home_tiles as ht

_VIEW = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "views" / "home_tiles.py"


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    h = hex_colour.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def test_a_gauge_runs_0_to_100_red_to_green_with_the_cursor_on_the_prediction() -> None:
    fig = ht.gate_gauge(0.07, "📈 1 200 streams / 28 j · 💶 84 €")
    ind = fig.data[0]
    assert tuple(ind.gauge.axis.range) == (0, 100)
    assert abs(ind.value - 7) < 1e-9 and abs(ind.gauge.threshold.value - 7) < 1e-9, (
        "the cursor is not where the prediction is")
    steps = ind.gauge.steps
    assert steps[0].range[0] == 0 and steps[-1].range[1] == 100
    first, last = _rgb(steps[0].color), _rgb(steps[-1].color)
    assert first[0] > first[1] and last[1] > last[0], "the gauge does not run red → green"


def test_the_amount_at_the_best_cpr_is_inside_the_gauge() -> None:
    sub = ht._gate_sub(1_200, 0.07)
    assert "84" in sub and "€" in sub
    fig = ht.gate_gauge(0.07, sub)
    assert [a.text for a in fig.layout.annotations] == [sub]


def test_no_number_no_gauge() -> None:
    """A cursor at 0 would read as « no chance » — no prediction draws no gauge."""
    assert ht.gate_gauge(None) is None and ht.gate_gauge(float("nan")) is None


def test_the_tiles_draw_the_gates_as_gauges() -> None:
    tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "render_tiles")
    called = {getattr(c.func, "id", "") for c in ast.walk(fn) if isinstance(c, ast.Call)}
    assert "_render_gate" in called, "the gates are no longer drawn as gauges"
