"""A utils helper does not draw one figure per registry entry — counted at RUNTIME.

Type: Sub
Uses: src/dashboard/utils/ml_widgets.py, src/dashboard/utils/algo_knowledge.py
Triggers: pytest
Depends on: nothing (a stubbed `st`; no database, no Streamlit runtime)
Persists in: nothing

Error class: too-many-charts-competing-for-one-decision (guard_scope: a utils helper that
draws in a loop over a registry).

Measured on the owner's dossier capture (R203, 2026-09-26, artist-1 snapshot): the
ml_performance page drew **44 figures, 38 of them from ONE line** —
`st.plotly_chart(_zone_bar_fig(spec, live))` inside `ml_widgets._render_one_gauge`, called
once per feature id of `ALGO_FEATURE_ZONES` (13+6+9) and `ALGO_VOLUME_ZONES` (4+0+6).

The first-screen guards count AST call SITES of renderers in `src/dashboard/views/**`. This
site lived in `utils/` and sat in a loop over a registry: one site, 38 figures, invisible
to both. A structural count proves an edge is DRAWN, not how many times it FIRES — so this
guard runs the helpers against a stub that records every call.
"""
from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.dashboard.utils import algo_knowledge as ak  # noqa: E402
from src.dashboard.utils import ml_widgets  # noqa: E402

_FIGURE_CALLS = ("plotly_chart", "pyplot", "altair_chart", "line_chart", "bar_chart",
                 "area_chart", "metric")


class _RecordingSt:
    """Just enough of `streamlit` for the gauge helpers — every call is counted."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str):
        def _record(*_a, **_k):
            self.calls.append(name)
            if name in ("expander", "container", "spinner"):
                return contextlib.nullcontext()
            if name == "columns":
                n = _a[0] if _a and isinstance(_a[0], int) else len(_a[0])
                return [self for _ in range(n)]
            return None
        return _record


def _draw(fn, algo: str, feats: dict) -> list[str]:
    stub = _RecordingSt()
    original = ml_widgets.st
    ml_widgets.st = stub
    try:
        fn(algo, feats)
    finally:
        ml_widgets.st = original
    return stub.calls


_CASES = [(fn, a) for a in ak.populated_algos()
          for fn in (ml_widgets.render_feature_gauges, ml_widgets.render_volume_gauges)]


def test_the_registry_is_big_enough_for_this_guard_to_mean_something() -> None:
    """ANTI-VACUITY: an emptied registry would make every count below trivially 0."""
    n = sum(len(ak.feature_ids(a)) + len(ak.volume_feature_ids(a))
            for a in ak.populated_algos())
    assert n >= 20, f"only {n} registry entries — the guard below would pass on nothing"


@pytest.mark.parametrize("feats", [{}, None], ids=["no-live-value", "none"])
@pytest.mark.parametrize("fn,algo", _CASES,
                         ids=[f"{f.__name__}-{a}" for f, a in _CASES])
def test_one_table_per_registry_never_a_figure_per_entry(fn, algo, feats) -> None:
    calls = _draw(fn, algo, feats)
    figures = [c for c in calls if c in _FIGURE_CALLS]
    assert not figures, (
        f"{fn.__name__}({algo!r}) drew {len(figures)} figure(s) {sorted(set(figures))} — "
        "one per registry entry is the defect this guard exists for (38 on "
        "ml_performance, 2026-09-26). Put the entries in ONE st.dataframe.")
    assert calls.count("dataframe") <= 1, (
        f"{fn.__name__}({algo!r}) emitted {calls.count('dataframe')} tables — one per "
        "(algo, registry), live and pedagogic rows together.")


def test_a_live_value_lands_in_the_table_not_in_a_figure() -> None:
    """With a REAL live value the table is drawn and still no figure is."""
    algo = "DW"
    live = [(f, s) for f, s in ak.ALGO_FEATURE_ZONES[algo].items()
            if ak.feature_live_available(s, {s["json_key"]: 1.0})]
    assert live, "no DW feature can carry a live value — the case below tests nothing"
    feats = {s["json_key"]: 1.0 for _f, s in live}
    calls = _draw(ml_widgets.render_feature_gauges, algo, feats)
    assert calls.count("dataframe") == 1
    assert not [c for c in calls if c in _FIGURE_CALLS]
    fid, spec = live[0]
    row = ml_widgets._gauge_row(algo, fid, spec, ml_widgets._live_value(algo, fid, spec, feats),
                                None)
    assert row[ml_widgets.t("ml_widgets.col_value", "Valeur")] != "—", row


def test_the_gap_reads_the_spec_bounds() -> None:
    spec = {"zones": [(0, 4000, "neutral", ""), (6000, None, "bonus", ""),
                      (4000, 6000, "neutral", "")]}
    assert ml_widgets._gap_to_bonus(spec, 5000) == 1000
    assert ml_widgets._gap_to_bonus(spec, 7000) == 0
    assert ml_widgets._gap_to_bonus(spec, None) is None
    assert ml_widgets._gap_to_bonus({"zones": [(0, None, "neutral", "")]}, 5) is None
    capped = {"zones": [(0, 10, "bonus", ""), (10, None, "malus", "")]}
    assert ml_widgets._gap_to_bonus(capped, 12) == -2
