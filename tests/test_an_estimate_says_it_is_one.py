"""R614 — a figure that draws an estimate beside a measure says which is which.

Type: Test
Uses: src/dashboard/utils/full_funnel.py, src/dashboard/views/trigger_algo/_forecast.py,
      src/dashboard/utils/platform_chart_notes.py, src/dashboard/utils/pdf_charts.py
Persists in: nothing

Inventory of 2026-10-15: of 17 figures, 2 mixed measured and estimated values without
saying so — the Meta × Spotify funnel (streams gained are a counterfactual, revenue is
that × €/stream, drawn like the measured budget) and the per-title forecast (a dotted
line with no legend entry, revenue at an assumed rate on measured points). A carried
counter level (home chart, PDF) was the third, smaller limit.

Every assertion reads the FIGURE object or the rendered text, never the source.

guard_scope: the funnel's labels, texts and note; the forecast's legend and hover/text;
the carried-level note and its PDF use. NOT covered: the home chart's caption (home is
frozen, R425 — a separate 🙋 row), a new figure that would mix the two.
"""
from __future__ import annotations

import pandas as pd

from src.dashboard.utils import full_funnel as ff
from src.dashboard.utils.platform_chart_notes import carried_level_note
from src.dashboard.views.trigger_algo import _forecast as fc

_FULL = {"spend": 100.0, "impressions": 20_000, "reach": 9_000, "link_clicks": 400,
         "arrivals": 200, "store_clicks": 100, "streams": 500}


def _funnel(m=_FULL, rate=0.004):
    return ff.figure(ff.steps(m, rate))


def test_every_estimated_step_and_figure_carries_the_mark() -> None:
    fig = _funnel()
    by_label = dict(zip(fig.data[0].y, fig.data[0].text))
    # Written here, not read from ff.ESTIMATED: a guard that reads the set it checks
    # stays green when the set loses a member.
    estimated = {ff._label(k) for k in ("streams", "revenue")}
    assert estimated <= set(by_label), "the fixture must draw both estimated steps"
    for label, text in by_label.items():
        parts = text.split(" · ")
        if label in estimated:
            assert label.startswith(ff.ESTIMATE_MARK), label
            # the derived ones too: « écoutes par clic », « % du budget récupéré »
            assert all(p.startswith(ff.ESTIMATE_MARK) for p in parts), text
        else:
            assert ff.ESTIMATE_MARK not in label + text, (label, text)


def test_the_funnel_says_what_the_mark_means_only_when_it_draws_one() -> None:
    assert ff.estimate_note(_funnel()), "an estimated step is drawn with no note"
    measured_only = _funnel({**_FULL, "streams": None}, None)
    assert ff.estimate_note(measured_only) is None
    assert ff.estimate_note(None) is None


def _hist(days: int) -> pd.DataFrame:
    return pd.DataFrame({"age": range(days),
                         "streams": [1000 * max(a, 1) ** -0.6 * (1.2 if a % 7 < 2 else 0.9)
                                     for a in range(days)]})


def _series(rate=None) -> dict:
    h = _hist(60)
    return {"name": "A", "path": fc.cumulative_path(h, fc.fit_decay(h)), "overlays": [],
            "rate": rate, "colour": "#444444"}


def test_the_dotted_line_has_a_legend_entry_naming_it_an_estimate() -> None:
    fig = fc.forecast_figure([_series()])
    keys = [tr for tr in fig.data if list(tr.x) == [None] and tr.mode == "lines"]
    assert len(keys) == 1 and keys[0].line.dash == "dot", [tr.name for tr in fig.data]
    assert keys[0].name and keys[0].showlegend is not False


def test_no_projection_no_projection_key() -> None:
    s = _series()
    s["path"] = [p for p in s["path"] if p["measured"]]
    fig = fc.forecast_figure([s])
    assert not [tr for tr in fig.data if list(tr.x) == [None] and tr.mode == "lines"]


def test_revenue_at_an_assumed_rate_is_marked_and_names_the_rate() -> None:
    fig = fc.forecast_figure([_series(rate=0.003)])
    euros = [x for tr in fig.data for x in (tr.text or ()) if x and "€" in x]
    assert euros and all("≈ " in x for x in euros), euros
    hovers = [h for tr in fig.data for h in (tr.hovertext or ()) if h and "€" in h]
    assert hovers and all("0,0030" in h for h in hovers), hovers[:2]


def test_a_carried_level_is_named_only_for_carried_platforms() -> None:
    note = carried_level_note(["youtube"], {"youtube": "YouTube"})
    assert note and "YouTube" in note
    assert carried_level_note([], {"youtube": "YouTube"}) is None


def test_the_pdf_evolution_figure_carries_the_note(monkeypatch) -> None:
    from datetime import date, timedelta

    from src.dashboard.utils import pdf_charts
    seen = []
    monkeypatch.setattr(pdf_charts, "_fig_to_uri",
                        lambda fig: seen.extend(t.get_text() for t in fig.texts) or "uri")
    d0 = date(2026, 6, 1)
    series = {"spotify": [(d0 + timedelta(i), 100 + i) for i in range(60)]}
    cum = {"youtube": [(d0 + timedelta(i), 1000 + 10 * i) for i in range(0, 60, 7)]}
    assert pdf_charts.platform_evolution(series, cum) == "uri"
    assert any("YouTube" in s for s in seen), seen
