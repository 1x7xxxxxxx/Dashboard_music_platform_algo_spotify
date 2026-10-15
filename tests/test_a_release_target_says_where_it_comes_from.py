"""R247 (fiche 42) — the Trigger Algo release panel: a target comes from the model or says
it is a reference, the gauge is the shortest route, and two versions of a title never
merge into one category.

Type: Test
Uses: src/dashboard/views/trigger_algo/_release_targets.py
"""
import math

import pandas as pd

from src.dashboard.views.trigger_algo import _release_targets as rt

# SavesLast28Days on DW: stored as-is (`_adj`), reference target 165 in the knowledge base.
_FEATS = {"SavesLast28Days_adj": 40.0}


def _curve_crossing_at(x_cross):
    """A fake model: P jumps above the 80 % target from `x_cross` on."""
    def curve(algo, key, feats, targets):
        xs = [0.0, 50.0, 100.0, 150.0, 200.0]
        return {"x_human": xs, "probs": [0.95 if x >= x_cross else 0.10 for x in xs]}
    return curve


def _never_crossing(algo, key, feats, targets):
    return {"x_human": [0.0, 100.0, 200.0], "probs": [0.1, 0.2, 0.3]}


def test_the_target_is_the_models_when_the_model_crosses():
    assert rt.model_target("DW", "SavesLast28Days", _FEATS, _curve_crossing_at(100)) == (
        100.0, "modèle")


def test_a_crossing_below_the_current_value_is_not_a_target():
    # The model already sits above 80 % at 0 — but the artist is at 40: a target BELOW
    # where they are would read as « already done » on a lever that is not.
    def curve(algo, key, feats, targets):
        return {"x_human": [0.0, 100.0], "probs": [0.9, 0.1]}
    assert rt.model_target("DW", "SavesLast28Days", _FEATS, curve) == (165.0, "repère")


def test_the_reference_is_labelled_as_such_when_the_model_never_crosses():
    assert rt.model_target("DW", "SavesLast28Days", _FEATS, _never_crossing) == (
        165.0, "repère")


def test_a_lever_that_is_not_the_algorithms_has_no_target():
    assert rt.model_target("RR", "SavesLast28Days", _FEATS, _never_crossing) == (None, None)


def test_the_gauge_is_the_lever_closest_to_its_target():
    levers = {("DW", "a"): {"current": 10, "target": 100, "source": "modèle", "progress": 0.1},
              ("DW", "b"): {"current": 60, "target": 100, "source": "repère", "progress": 0.6},
              ("RADIO", "a"): {"current": 90, "target": 100, "source": "modèle", "progress": 0.9}}
    route = rt.shortest_route(levers, "DW")
    assert route["lever"] == "b" and math.isclose(route["progress"], 0.6)
    assert rt.shortest_route(levers, "RR") is None


def test_track_levers_caps_progress_and_keeps_the_source():
    out = rt.track_levers(_FEATS, _curve_crossing_at(100))
    saves = out[("DW", "SavesLast28Days")]
    assert saves["source"] == "modèle" and math.isclose(saves["progress"], 0.4)


def test_the_latest_releases_come_first_and_unknown_age_last():
    df = pd.DataFrame({"song": ["old", "new", "unknown", "mid"],
                       "days_since_release": [900, 3, None, 40]})
    assert rt.last_releases(df, 3) == ["new", "mid", "old"]


def test_two_versions_of_a_title_never_share_a_label():
    tracks = ["Je ne parle pas très bien le français - Original",
              "Je ne parle pas très bien le français - Remix", "Court", "Court"]
    labels = rt.short_labels(tracks, 18)
    assert len(set(labels)) == len(labels)
    assert labels[2] == "Court"
    assert labels[0].endswith("Original") and labels[1].endswith("Remix")
    # The panel goes through the shared helper — one rule for a cut title (R209).
    from src.dashboard.utils.labels import unique_short_labels
    assert rt.short_labels is unique_short_labels


def _lever(cur, target, source="repère"):
    return {"current": cur, "target": target, "source": source, "progress": min(cur / target, 1)}


def test_the_values_figure_is_one_panel_per_playlist_one_bar_per_track():
    # R559 (fiche 47): DW → Radio → RR, a bar per track, the two numbers written on it.
    levers = {s: {("DW", "SavesLast28Days"): _lever(4.0, 165.0),
                  ("DW", "StreamsLast7Days"): _lever(300.0, 1000.0, "modèle"),
                  ("RR", "SavesLast28Days"): _lever(4.0, 50.0),
                  ("RADIO", "StreamsLast7Days"): _lever(300.0, 900.0, "modèle")}
              for s in ("A - Original", "A - Remix")}
    fig = rt.values_figure(["A - Original", "A - Remix"], levers)
    # R602 — each panel is named on its LEFT by the gauges' pill, and 100 % is named.
    pills = [a for a in fig.layout.annotations if a.bgcolor]
    assert [p.text.split("</b>")[0] for p in pills] == [
        f"<b>{rt.ALGO_NAMES[a]}" for a in ("DW", "RADIO", "RR")], [p.text for p in pills]
    assert all(p.x == 0.0 and p.xanchor == "left" and p.yanchor == "middle" for p in pills)
    assert min(fig.layout.xaxis.domain) > 0.3, "the bars leave the left to the pills"
    assert any("100 %" in (a.text or "") for a in fig.layout.annotations if not a.bgcolor)
    dw = [tr for tr in fig.data if tr.xaxis == "x"]
    assert len(dw) == 2 and len({tr.name for tr in dw}) == 2, "one bar per track"
    assert all(tr.marker.color == rt.ALGO_COLORS["DW"] for tr in dw)
    assert any("4 / 165 (repère)" in (txt or "") for txt in dw[0].text)
    assert rt.values_figure(["A"], {}) is None


def test_the_values_figure_sorts_levers_by_weight():
    levers = {"A": {("DW", "SavesLast28Days"): _lever(4.0, 165.0),
                    ("DW", "StreamsLast7Days"): _lever(300.0, 1000.0)}}
    key = rt.ALGO_FEATURE_ZONES["DW"]["SavesLast28Days"].get("json_key", "SavesLast28Days")
    label = rt.ALGO_FEATURE_ZONES["DW"]["SavesLast28Days"]["label"]
    # Saves come AFTER streams in the fixed order; a heavy weight puts them first.
    assert rt.values_figure(["A"], levers).data[0].y[0] != label, "fixed order without weights"
    assert rt.values_figure(["A"], levers, {"DW": {key: 5.0}}).data[0].y[0] == label


def test_the_heaviest_three_features_come_first():
    w = {"DW": {"a": 0.1, "b": 0.9, "c": 0.5, "d": 0.0, "e": 0.3}}
    assert rt.top_features(w, "DW") == ["b", "c", "e"]
    assert rt.top_features(w, "RR") == []


def test_lever_weights_average_the_absolute_shap(monkeypatch):
    import numpy as np

    from src.utils import shap_explain
    from src.utils.ml_inference import FEATURE_COLUMNS

    class _Exp:
        def __init__(self, n):
            self.values = np.tile([[-2.0] + [0.0] * (len(FEATURE_COLUMNS) - 1)], (n, 1))
            self.values[0, 0] = 4.0
    monkeypatch.setattr(shap_explain, "explain", lambda model, X: _Exp(len(X)))
    w = rt.lever_weights({"a": {}, "b": {}},
                         loader=lambda name: None if name == "rr_classifier" else object())
    assert set(w) == {"DW", "RADIO"}, "a missing model is left out"
    assert w["DW"][FEATURE_COLUMNS[0]] == 3.0, "mean of |4| and |-2|"
    assert rt.lever_weights({}, loader=lambda n: object()) == {}


_EST = {"estimates": {a: {"j28": {"p25": 200, "p50": 500, "p75": 1400, "n": 40},
                          "m6": {"n": 3, "refused": True}, "y1": {"n": 0, "refused": True}}
                      for a in ("dw", "rr", "radio")}}


def _three_levers(current: float, target: float) -> dict:
    return {"A": {(a, "StreamsLast7Days"): _lever(current, target, "modèle")
                  for a in ("DW", "RADIO", "RR")}}


def test_each_gauge_prices_the_streams_gap_at_the_best_cpr():
    """R581 (owner, 2026-10-15) — under each gauge: the 7-day streams still missing, the
    Meta budget to buy them at the BEST CPR, and what the playlist brings once triggered."""
    money = {"cpr": 0.05, "rate": {"A": 0.004}, "est": _EST}
    fig = rt.indicators_figure(["A"], _three_levers(300.0, 1000.0), money=money)
    lines = [a.text for a in fig.layout.annotations if "≈" in (a.text or "")
             and "de pub" in (a.text or "")]
    assert len(lines) == 3, "one budget line per gauge"
    assert all("700" in x and "35 €" in x for x in lines), lines   # 700 × 0,05 €
    assert all("500 écoutes" in x and "2 €" in x for x in lines), lines   # P50 × 0,004 €
    assert all(tr.number.font.size >= 30 for tr in fig.data if tr.type == "indicator")


def test_no_budget_is_invented_without_a_cpr_or_past_the_target():
    fig = rt.indicators_figure(["A"], _three_levers(300.0, 1000.0),
                               money={"cpr": None, "rate": {}, "est": {}})
    assert not [a for a in fig.layout.annotations if "€" in (a.text or "")]
    met = rt.money_line(_three_levers(1200.0, 1000.0)["A"], "DW", {"cpr": 0.05}, "A")
    assert "atteint" in met and "€" not in met


def test_the_pill_gives_each_criterion_its_shap_share_and_its_value():
    """R580 — « déclenché par » names each criterion's share of the decision and its
    current value per title; a `_log` column is shown back in streams."""
    w = {"DW": {"StreamsLast7Days_log": 3.0, "SavesLast28Days_adj": 1.0, "x": 0.0}}
    feats = {"A": {"StreamsLast7Days_log": math.log1p(99.0), "SavesLast28Days_adj": 12.0}}
    box = rt._playlist_box("DW", w, feats)
    assert "75 %" in box and "25 %" in box, box
    assert "99" in box and "12" in box, box
    assert rt.shap_share({}, "DW", "x") is None


def test_the_comparison_defaults_to_the_release_before_the_reference():
    """R579 — two filters; the comparison's index 1 is the second-newest, « none » first."""
    opts = rt.comparison_options(["new", "old", "older"], "new")
    assert opts == [None, "old", "older"]
    assert rt.comparison_options(["new", "old"], "old") == [None, "new"]


def test_a_trigger_brings_is_drawn_beside_each_playlist():
    """R583 — the cohort's 28-day streams sit in a last column, one panel per playlist."""
    readings = {"A": pd.DataFrame({"age_days": [27], "DW": [420.0], "RADIO": [900.0],
                                   "RR": [700.0]})}
    fig = rt.indicators_figure(["A"], _three_levers(300.0, 1000.0),
                               money={"cpr": 0.05, "rate": {}, "est": _EST}, readings=readings)
    xy = [tr for tr in fig.data if tr.type == "scatter"]
    pred = [tr for tr in xy if tr.legendgroup == "pred"]
    assert len(pred) == 3 and all(tr.line.dash == "dot" for tr in pred)
    assert len({tr.xaxis for tr in pred}) == 3, "one panel per playlist"
    real = [tr for tr in xy if (tr.legendgroup or "").startswith("real-")]
    assert len(real) == 3 and all(tr.mode == "markers" for tr in real)
    assert any("rapporte" in (a.text or "") for a in fig.layout.annotations)
    assert not [tr for tr in rt.indicators_figure(["A"], _three_levers(1, 2)).data
                if tr.type != "indicator"], "no estimates, no column"


def test_the_best_cpr_is_said_once_not_under_each_gauge():
    """R581 — repeated under every gauge, the CPR made each line wider than its gauge and
    two neighbours overlapped (`test_a_rendered_figure_is_laid_out[trigger_algo]`)."""
    fig = rt.indicators_figure(["A", "B"], {**_three_levers(300.0, 1000.0),
                                            "B": _three_levers(300.0, 1000.0)["A"]},
                               money={"cpr": 0.068, "rate": {}, "est": {}})
    texts = [a.text or "" for a in fig.layout.annotations]
    assert sum("0,068" in x for x in texts) == 1, texts
    assert any("de pub" in x and "0,068" not in x for x in texts), texts


def test_each_pill_is_centred_on_its_row_of_gauges():
    """R600 (owner, 2026-10-15) — « pastilles alignées sur leur rangée de jauges »: with
    `yanchor` left to « auto », the top pill hung from its top and the bottom one stood on
    its bottom. Each pill's vertical centre is its row's."""
    fig = rt.indicators_figure(["A", "B"], {**_three_levers(300.0, 1000.0),
                                            "B": _three_levers(300.0, 1000.0)["A"]})
    pills = [a for a in fig.layout.annotations if a.bgcolor]
    gauges = [tr for tr in fig.data if tr.type == "indicator"]
    rows = sorted({tuple(tr.domain.y) for tr in gauges}, reverse=True)
    assert len(pills) == len(rows) == 3
    for pill, (y0, y1) in zip(pills, rows):
        assert pill.yanchor == "middle" and abs(pill.y - (y0 + y1) / 2) < 1e-9
    assert "machine learning" in rt._playlist_box("DW", {"DW": {"StreamsLast7Days_log": 1.0}})
