"""R244 — charts merged at the owner's request keep every series readable and honest.

Owner, 2026-09-27: fiche 5 « fusionner les deux », 18/19/63 « tout sur un même graphique,
des cumuls », 31 and 35 « un seul graphique », 67-69 « fusionner, deux légendes ».
"""
import datetime as dt

import pandas as pd
import plotly.graph_objects as go

from src.dashboard.utils.charts import to_base100
from src.dashboard.utils.treasury_chart import source_cumuls


def test_an_index_starts_at_its_first_positive_value_and_keeps_the_real_one():
    fig = go.Figure([go.Scatter(x=[1, 2, 3], y=[0, 50, 100], name="streams"),
                     go.Bar(x=[1, 2, 3], y=[0, 0, 0], name="vide")])
    one, skipped = to_base100(fig)
    tr = one.data[0]
    assert list(tr.y) == [None, 100.0, 200.0] or list(tr.y)[1:] == [100.0, 200.0]
    assert list(tr.customdata) == [0, 50, 100], "the hover lost the real value"
    assert skipped == ["vide"], "a series without a base must be NAMED, not drawn at 0"


def test_a_release_peak_is_clipped_and_said():
    ys = [10] + [10] * 50 + [1000] + [10] * 50
    one, _ = to_base100(go.Figure([go.Scatter(x=list(range(len(ys))), y=ys, name="s")]))
    assert one.layout.yaxis.range and one.layout.yaxis.range[1] < 1000 * 10
    assert any("hors échelle" in (a.text or "") for a in one.layout.annotations)


def test_money_cumulates_by_source_with_its_sign_and_never_drops_back():
    d = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-03-01", "2024-01-01"]),
        "flux": ["revenu", "revenu", "depense"], "source": ["imusician", "imusician", "meta_ads"],
        "amount_eur": [10.0, 5.0, 100.0]})
    months = pd.date_range("2024-01-01", periods=3, freq="MS")
    cum = source_cumuls(d, months)
    assert list(cum["imusician"]) == [10.0, 10.0, 15.0], "a month without sale carries the total"
    assert list(cum["meta_ads"]) == [-100.0, -100.0, -100.0], "spend falls below zero"


def test_the_usage_chart_has_two_legends_and_names_the_rest():
    from src.dashboard.views.usage_analytics import _TOP_PAGES, usage_figure
    day = dt.date(2026, 9, 1)
    rows = [(day, "page_view", f"p{i}", 10 - i) for i in range(_TOP_PAGES + 3)]
    rows += [(day, "login", "—", 4), (day, "error", "—", 1)]
    fig = usage_figure(pd.DataFrame(rows, columns=["jour", "event", "page", "n"]))
    groups = {tr.legendgroup for tr in fig.data}
    assert groups == {"pages", "events"}
    names = {tr.name for tr in fig.data if tr.legendgroup == "pages"}
    assert len(names) == _TOP_PAGES + 1 and "autres pages" in names
    assert sum(sum(tr.y) for tr in fig.data) == sum(r[3] for r in rows), "an event was lost"
