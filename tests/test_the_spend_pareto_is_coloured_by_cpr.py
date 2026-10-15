"""R596 — « où est passé l'argent » : the spend bars say the CPR by their colour.

Type: Sub
Uses: src.dashboard.views.meta_creatives (_pareto_figure)
Depends on: nothing (pure figure)
Persists in: nothing
"""
from __future__ import annotations

import pandas as pd

from src.dashboard.views.meta_creatives import _pareto_figure


def _frame() -> pd.DataFrame:
    return pd.DataFrame({"campaign_name": ["A", "A", "B"],
                         "label": ["A › s › x", "A › s › y", "B › s › z"],
                         "total_spend": [300.0, 200.0, 100.0],
                         "cpr": [0.5, 2.0, None]})


def test_the_bar_colour_is_the_cpr_on_a_named_scale() -> None:
    fig = _pareto_figure(_frame())
    priced = fig.data[0]
    assert dict(zip(priced.y, priced.marker.color)) == {"A › s › y": 2.0, "A › s › x": 0.5}
    assert priced.marker.showscale and priced.marker.colorscale
    assert "CPR" in priced.marker.colorbar.title.text
    assert all("CPR" in x for x in priced.text)


def test_a_bar_without_cpr_is_grey_and_off_the_scale() -> None:
    grey = _pareto_figure(_frame()).data[1]
    assert list(grey.y) == ["B › s › z"] and grey.marker.color == "#9E9E9E"
    assert "—" in grey.text[0]
