"""The algo page explains each playlist from ONE source per answer (R381).

Type: Guard
Uses: src.dashboard.views.trigger_algo._playlist_detail, src.dashboard.utils.algo_preview_data,
  src.dashboard.views.meta_cpr_optimizer
Depends on: nothing (pure functions, fixtures)
Persists in: nothing

Owner's notes V56, V64, V66, V71 (2026-10-05). Three answers, three single sources
(the threshold bars and their shared cost left with R559, fiche 56): the cost is a RANGE
from one shared function; the SHAP list skips a floor probability and keeps the one playlist order;
the recommendations are the CPR Optimizer's own, filtered to one title.

Mutations, 2026-10-05:
  - `budget_fourchette` returning (best, best) → RED;
  - the median-spend floor dropped from `cpr_bornes` → RED (best = the 18 € boost);
  - the floor exclusion removed from `shap_par_playlist` → RED;
  - `for_track` matching the raw name instead of the canonical one → RED.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

# Artist 1's campaigns as read on 2026-10-05 (name, spend €, results) — frozen.
_CAMPAIGNS = [
    ("Publication boost", 18.41, 1670), ("CONKRETE TECHNO", 353.18, 5156),
    ("O chiotte", 755.52, 6932), ("Qui a bu", 684.98, 5216),
    ("QASMS Remix - 1", 59.31, 434), ("KSD Brésil", 43.77, 316),
    ("JNPPTBFR", 425.96, 2970), ("QASMS rév1", 224.98, 1139),
    ("CATEDERPAS", 40.04, 161), ("Hypeddit ar4z6p", 11.42, 33),
]


def test_the_cost_is_a_range_from_the_shared_function() -> None:
    from src.dashboard.utils.algo_preview_data import budget_fourchette, budget_pour_streams

    assert budget_fourchette(1000, (0.07, 0.12)) == (
        budget_pour_streams(1000, 0.07), budget_pour_streams(1000, 0.12))
    assert budget_fourchette(None, (0.07, 0.12)) is None
    assert budget_fourchette(1000, None) is None



def test_the_cpr_bounds_on_a_frozen_account() -> None:
    from src.dashboard.utils.algo_preview_data import cpr_bornes

    best, mean = cpr_bornes(_CAMPAIGNS)
    # The 18 € boost (0,011 €) is under the median spend: it is luck, not a bound.
    assert best == pytest.approx(353.18 / 5156)
    total_spend = sum(s for _n, s, _r in _CAMPAIGNS)
    assert mean == pytest.approx(total_spend / sum(r for _n, _s, r in _CAMPAIGNS))
    assert best <= mean
    assert cpr_bornes([]) is None


class _Exp:
    def __init__(self, values):
        self.values = np.array([values])


def test_shap_skips_a_floor_playlist_and_sorts_by_weight(monkeypatch) -> None:
    from src.dashboard.views.trigger_algo import _playlist_detail as pd_
    from src.utils import shap_explain
    from src.utils.ml_inference import FEATURE_COLUMNS

    weights = np.linspace(-1, 1, len(FEATURE_COLUMNS))
    monkeypatch.setattr(shap_explain, "explain", lambda model, X: _Exp(weights))
    pred = {"dw_probability": 0.6, "radio_probability": 0.0001, "rr_probability": 0.5}
    shown, floored = pd_.shap_par_playlist({FEATURE_COLUMNS[0]: 1.0}, pred,
                                           loader=lambda key: object())
    assert [s["algo"] for s in shown] == ["DW", "RR"]
    assert floored == ["Radio"], "a floor probability was explained"
    mags = [abs(c["shap"]) for c in shown[0]["contribs"]]
    assert mags == sorted(mags, reverse=True) and len(mags) == pd_.TOP
    missing = {c["feature"]: c["missing"] for c in shown[0]["contribs"]}
    assert missing.get(FEATURE_COLUMNS[0]) is False
    assert any(missing.values()), "an absent criterion is not marked missing"


def test_the_recommendations_are_the_optimizers_filtered_to_one_title() -> None:
    from src.dashboard.views.meta_cpr_optimizer import _compute_scores, for_track

    df = pd.DataFrame({
        "campaign_name": ["A", "B", "C"],
        # C carries the real « : », the prediction the filename-derived « _ »:
        # the SQL join matches them (canonical_song), so must the filter.
        "track_name": ["Kimono_ Remix", "Autre titre", "KIMONO: Remix"],
        "total_spend": [353.18, 755.52, 40.04], "total_results": [5156, 6932, 161],
        "cpr": [353.18 / 5156, 755.52 / 6932, 40.04 / 161],
        "dw_prob": [None] * 3, "rr_prob": [None] * 3, "radio_prob": [None] * 3})
    scored = _compute_scores(df, cpr_median=0.11, k_confiance=1244)
    mine = for_track(scored, "Kimono_ Remix")
    assert list(mine["campaign_name"]) == ["A", "C"], list(mine["campaign_name"])
    assert list(mine["budget_delta"]) == ["+30%", "-30%"]
    assert for_track(scored, None).empty
