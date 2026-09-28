"""R298 — the review dossier resolves Streamlit's colour placeholders before drawing.

Type: Test
Uses: pytest, plotly, streamlit
Depends on: tools/dev/charts_dossier/capture.py (resolve_theme_placeholders)
Persists in: nothing

Measured 2026-09-28: once Streamlit is imported, `pio.templates.default` is "streamlit",
whose colorway is #000001…#000010 — placeholders its FRONTEND swaps for theme colours. A
plotly-express figure without explicit colours, re-rendered off-screen by the dossier,
came out in near-black: fiche 66 (admin costs) showed four black bars.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "dev" / "charts_dossier"))
from capture import resolve_theme_placeholders  # noqa: E402


def _px_spec_under_streamlit() -> str:
    import plotly.express as px
    import streamlit.elements.plotly_chart  # noqa: F401 — installs the "streamlit" template
    fig = px.bar(pd.DataFrame({"x": [1, 2], "y": [1, 2], "c": ["a", "b"]}),
                 x="x", y="y", color="c")
    return fig.to_json()


def test_the_premise_a_px_figure_under_streamlit_carries_placeholders() -> None:
    spec = _px_spec_under_streamlit()
    assert "#000001" in spec, "Streamlit no longer injects placeholders — this guard is moot"


def test_every_placeholder_is_resolved_to_a_visible_colour() -> None:
    spec, n = resolve_theme_placeholders(_px_spec_under_streamlit())
    assert n > 0
    for k in range(1, 11):
        assert f"#0000{k:02d}" not in spec.lower(), f"#0000{k:02d} left near-black"
    assert "#0068c9" in spec and "#83c9ff" in spec   # first two series, distinct


def test_a_real_near_black_colour_is_left_alone() -> None:
    spec, n = resolve_theme_placeholders('{"marker": {"color": "#000011"}}')
    assert n == 0 and "#000011" in spec
