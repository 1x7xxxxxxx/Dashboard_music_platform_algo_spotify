"""A volume forecast the reliability gate suppresses is never drawn on the Model tab.

Type: Test
Uses: pytest, streamlit.testing.v1.AppTest, json
Depends on: src/dashboard/views/trigger_algo/_tab_model.py,
            src/dashboard/utils/algo_knowledge.py (ALGO_REGRESSOR_METRICS,
            volume_forecast_reliable)
Persists in: nothing

What was measured (2026-09-26, on the prod snapshot `spotify_etl_review`)
-------------------------------------------------------------------------
`ak.volume_forecast_reliable("RR")` is False: the product decided the Release Radar
volume is noise (R²=0.23) and must not be shown. `_verdict.py` and
`revenue_forecast.py` honour that gate. The Model tab did not: it drew the RR
scatter unconditionally and read the gate only to add a caption under it, so the
one forecast the product refuses to show was the one plotted. 683 of 685 stored RR
forecasts were 0, so the chart was a column of dots at x=0.

Both remaining scatters also plotted an ALGO-SOURCED 28-day forecast
(`machine_learning/train.py:122-128`) against `streams_7d`, ALL-source 7-day
streams, with a y=x "Prédiction parfaite" line and "streams 7j" on both axes. No
algo-sourced actual exists in the schema, so that diagonal measured nothing.

What this guard reads
---------------------
The RENDERED figures, not the source: `at.get("plotly_chart")` returns an element
whose `.proto.spec` is the serialized Plotly figure (checked on Streamlit 1.54.0,
which has no native plotly accessor on AppTest). A trace whose x-values equal an
algo's forecast column is that algo's forecast being drawn, whatever the code
around it is called. The gate is flipped per test through the registry itself, so
a fix hard-coding `"RR"` goes red on the Radio case.

Mutations seen red (2026-09-26), each file restored from a copy and checked by `cmp`
-----------------------------------------------------------------------------------
* the original `_tab_model.py` put back byte for byte: "DW volume forecast is DRAWN
  although volume_forecast_reliable('DW') is False", "RADIO flipped … still drawn",
  and the "Prédiction parfaite" assertion;
* RR alone exempted from the gate (`and algo != "RR"`): "RR volume forecast is DRAWN";
* the gate replaced by the literal `algo in ("DW", "RR")`: only the registry-flip test;
* the y=x trace re-added: only the axis test;
* `drop_suppressed_floor_columns` narrowed back to the RR literal: "dw_streams_forecast_7d
  kept although volume_forecast_reliable('DW') is False".
"""
from __future__ import annotations

import json

import pytest
from streamlit.testing.v1 import AppTest

from src.dashboard.utils import algo_knowledge as ak

# Distinct values per algo, so a drawn trace names its algo unambiguously.
FORECASTS = {
    "DW": [1111.0, 1212.0, 1313.0],
    "RR": [2221.0, 2323.0, 2424.0],
    "RADIO": [3331.0, 3434.0, 3535.0],
}
ACTUAL = [10.0, 20.0, 30.0]


def _script() -> None:
    import pandas as pd

    from src.dashboard.views.trigger_algo._tab_model import _show_tab_model
    from tests.test_a_suppressed_forecast_is_never_drawn import ACTUAL, FORECASTS

    class _FakeDB:
        def fetch_df(self, _query, _params=None):
            # R247 (fiche 51): one row per title — the S4A reading of each algorithm's
            # 28-day streams, and the latest forecast made before it.
            return pd.DataFrame({
                "song": ["a", "b", "c"],
                "dw_streams": ACTUAL, "rr_streams": ACTUAL, "radio_streams": ACTUAL,
                "predicted_dw": FORECASTS["DW"],
                "predicted_rr": FORECASTS["RR"],
                "predicted_radio": FORECASTS["RADIO"],
            })

    _show_tab_model(_FakeDB(), "Some Song", 999)


def _render() -> AppTest:
    at = AppTest.from_function(_script, default_timeout=30)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _traces(at: AppTest) -> list[dict]:
    out = []
    for el in at.get("plotly_chart"):
        spec = json.loads(el.proto.spec)
        out.extend(spec.get("data", []))
    return out


def _drawn_x(at: AppTest) -> list[list[float]]:
    """Numeric x- AND y-series of every drawn trace; date/category axes are skipped.

    Both axes: since R247 (fiche 51) a forecast is a bar HEIGHT per title, no longer an x
    position — reading x alone would have let a suppressed forecast through as a bar."""
    out = []
    for tr in _traces(at):
        for axis in ("x", "y"):
            vals = tr.get(axis, [])
            assert isinstance(vals, list), (
                f"{axis} is not a plain list ({type(vals).__name__}): the serialization "
                f"changed, this guard can no longer read what is drawn")
            try:
                out.append([float(v) for v in vals])
            except (TypeError, ValueError):
                continue
    return out


def _texts(at: AppTest) -> str:
    return "\n".join(str(getattr(e, "value", "")) for e in (*at.info, *at.caption))


def suppressed_forecasts_drawn(drawn: list[list[float]]) -> list[str]:
    """The detector: algos whose forecast is drawn although the gate suppresses it."""
    return [algo for algo, values in FORECASTS.items()
            if not ak.volume_forecast_reliable(algo) and values in drawn]


def perfect_prediction_traces(traces: list[dict]) -> list[str]:
    """The detector: y=x "perfect prediction" traces (the two axes are not one quantity)."""
    return [str(tr.get("name", "")) for tr in traces
            if "parfaite" in str(tr.get("name", "")).lower()
            or "perfect" in str(tr.get("name", "")).lower()]


def _assert_matches_gate(at: AppTest) -> None:
    drawn = _drawn_x(at)
    for algo in suppressed_forecasts_drawn(drawn):
        raise AssertionError(
            f"{algo} volume forecast is DRAWN although volume_forecast_reliable("
            f"{algo!r}) is False — the gate must decide whether the chart exists, "
            f"not add a caption under it")
    for algo, values in FORECASTS.items():
        if ak.volume_forecast_reliable(algo):
            assert values in drawn, (
                f"{algo} volume is reliable per the gate but its forecast is not drawn")
            continue
        note = ak.volume_suppressed_note(algo)
        if note:
            assert note[:40] in _texts(at), (
                f"{algo} is suppressed but its suppressed note is not shown")


def test_the_registry_gate_decides_every_scatter() -> None:
    """Today's registry: DW and RR suppressed, Radio shown."""
    assert not ak.volume_forecast_reliable("RR")  # premise of the defect
    _assert_matches_gate(_render())


def test_the_gate_is_read_not_a_literal_rr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flip RADIO to unreliable in the registry: its scatter must disappear too."""
    radio = dict(ak.ALGO_REGRESSOR_METRICS["RADIO"], volume_reliable=False,
                 suppressed_note="Radio volume suppressed for this test.")
    monkeypatch.setitem(ak.ALGO_REGRESSOR_METRICS, "RADIO", radio)
    at = _render()
    assert FORECASTS["RADIO"] not in _drawn_x(at), (
        "RADIO flipped to volume_reliable=False in the registry but its forecast "
        "is still drawn — the tab gates on a literal, not on the registry")
    _assert_matches_gate(at)


_FLOOR_COLS = {"DW": "dw_streams_forecast_7d", "RR": "rr_streams_forecast_7d",
               "RADIO": "radio_streams_forecast_7d"}


@pytest.mark.parametrize("flip", [None, "RADIO"])
def test_the_roi_table_drops_every_suppressed_floor_column(
        flip: str | None, monkeypatch: pytest.MonkeyPatch) -> None:
    """revenue_forecast read only "RR": the DW floor column stayed in the ROI table."""
    import pandas as pd

    from src.dashboard.views.revenue_forecast import drop_suppressed_floor_columns

    if flip:
        monkeypatch.setitem(ak.ALGO_REGRESSOR_METRICS, flip,
                            dict(ak.ALGO_REGRESSOR_METRICS[flip], volume_reliable=False))
    df = pd.DataFrame({"song": ["s"], **{c: [1] for c in _FLOOR_COLS.values()}})
    kept = set(drop_suppressed_floor_columns(df).columns)
    for algo, col in _FLOOR_COLS.items():
        assert (col in kept) == ak.volume_forecast_reliable(algo), (
            f"{col} {'kept' if col in kept else 'dropped'} although "
            f"volume_forecast_reliable({algo!r}) is {ak.volume_forecast_reliable(algo)}")


def test_no_scatter_claims_a_forecast_and_an_actual_are_one_quantity() -> None:
    """No y=x "perfect prediction" line: the two axes carry different quantities."""
    at = _render()
    for name in perfect_prediction_traces(_traces(at)):
        raise AssertionError(
            f"a y=x {name!r} trace compares an algo-sourced 28-day forecast with "
            f"all-source 7-day streams as if they were one quantity")
    for el in at.get("plotly_chart"):
        layout = json.loads(el.proto.spec).get("layout", {})
        x_title = json.dumps(layout.get("xaxis", {}).get("title", ""))
        y_title = json.dumps(layout.get("yaxis", {}).get("title", ""))
        assert x_title != y_title, "both axes carry the same label"


# ── The proof: the detectors see the shape they are written for ────────────────

def _defective_script() -> None:
    """The pre-2026-09-26 shape: every forecast scattered, each with a y=x line."""
    import plotly.graph_objects as go
    import streamlit as st

    from tests.test_a_suppressed_forecast_is_never_drawn import ACTUAL, FORECASTS

    for values in FORECASTS.values():
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=values, y=ACTUAL, mode="markers", name="Points"))
        fig.add_trace(go.Scatter(x=[0, 4000], y=[0, 4000], mode="lines",
                                 name="Prédiction parfaite"))
        st.plotly_chart(fig)


def _clean_script() -> None:
    """The corrected shape: only the gate-allowed forecast, no diagonal."""
    import plotly.graph_objects as go
    import streamlit as st

    from src.dashboard.utils import algo_knowledge as ak
    from tests.test_a_suppressed_forecast_is_never_drawn import ACTUAL, FORECASTS

    for algo, values in FORECASTS.items():
        if ak.volume_forecast_reliable(algo):
            st.plotly_chart(go.Figure(go.Scatter(x=values, y=ACTUAL, name=algo)))


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    bad = AppTest.from_function(_defective_script, default_timeout=30)
    bad.run()
    assert not bad.exception
    expected = [a for a in FORECASTS if not ak.volume_forecast_reliable(a)]
    assert expected, "premise: at least one algo is suppressed in the registry"
    assert suppressed_forecasts_drawn(_drawn_x(bad)) == expected
    assert perfect_prediction_traces(_traces(bad)), "the y=x trace went unseen"

    good = AppTest.from_function(_clean_script, default_timeout=30)
    good.run()
    assert not good.exception
    assert suppressed_forecasts_drawn(_drawn_x(good)) == []
    assert perfect_prediction_traces(_traces(good)) == []
