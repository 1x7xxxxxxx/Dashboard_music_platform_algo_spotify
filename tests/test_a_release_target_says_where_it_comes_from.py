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


def test_the_values_figure_draws_one_slot_per_track():
    levers = {s: {("DW", "SavesLast28Days"): {"current": 4.0, "target": 165.0,
                                               "source": "repère", "progress": 0.02}}
              for s in ("A - Original", "A - Remix")}
    fig = rt.values_figure(["A - Original", "A - Remix"], levers)
    assert len(set(fig.layout.xaxis3.ticktext)) == 2
    marker = next(tr for tr in fig.data if tr.type == "scatter").marker
    assert marker.color == rt.ALGO_COLORS["DW"], "an unset marker colour draws black"
