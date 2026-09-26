"""The Créatives funnel draws stages that nest, each under its own name.

Type: Hook (guard)
Uses: src.dashboard.views.meta_creatives.funnel_stages
Persists in: nothing

Measured 2026-09-26 on spotify_etl_review, v_meta_creative_daily, artist 1: the funnel
was impressions → `clicks` → `conversions`, the last one labelled « Clics sortants ».
`clicks` is Meta clicks (all); `conversions` is the ad set goal's result — the Hypeddit
outbound event counted twice, or a video view under THRUPLAY. 18 of the 61
(creative, campaign) rows with spend widened. The two rows below are those measured
rows, byte for byte; their link_clicks / outbound values do not exist yet at the ad
grain (migration 138, pending re-collection) and are ILLUSTRATIVE, chosen consistent
with the campaign grain (outbound <= link clicks <= clicks (all), 0 exceptions on 16
campaigns).

Class: a-proxy-rendered-under-the-name-of-the-thing-it-proxies.
"""
from __future__ import annotations

import math

import pandas as pd

from src.dashboard.views.meta_creatives import funnel_stages

_NAN = math.nan


def _row(campaign: str, imp: int, clicks: int, results: int,
         link: float = _NAN, outbound: float = _NAN) -> dict:
    return {"creative_name": "x", "campaign_name": campaign,
            "total_impressions": imp, "total_clicks": clicks, "total_results": results,
            "total_link_clicks": link, "total_outbound": outbound}


def _values(stages):
    return [v for _, _, v in stages]


def _labels(stages):
    return [label for _, label, _ in stages]


def test_the_measured_widening_row_now_nests() -> None:
    """Drop Hook 2 You absolutely / O chiotte…: 2 732 → 48 → 60 before the fix."""
    df = pd.DataFrame([_row("O chiotte", 2732, 48, 60, link=40, outbound=30)])
    stages = funnel_stages(df)
    assert _values(stages) == [2732, 40, 30], _values(stages)
    assert _labels(stages) == ["Impressions", "Clics sur le lien", "Clics sortants"]
    vals = _values(stages)
    assert all(a >= b for a, b in zip(vals, vals[1:])), f"funnel widens: {vals}"


def test_a_goal_result_is_never_drawn_as_outbound_clicks() -> None:
    """« New HardTechno release » (THRUPLAY): 2 028 → 7 → 1 670 video views."""
    df = pd.DataFrame([_row("thruplay", 2028, 7, 1670)])
    stages = funnel_stages(df)
    assert ("Clics sortants" not in _labels(stages)
            and 1670 not in _values(stages)), stages
    # Link clicks not collected yet: stage 2 is clicks (all), under THAT name.
    assert stages == [("meta_creatives.impressions", "Impressions", 2028),
                      ("meta_creatives.clicks_all", "Clics (tous types)", 7)]


def test_one_creative_in_two_campaigns_is_summed_not_picked() -> None:
    """« Début » runs in two campaigns; `.iloc[0]` showed one under the bare name."""
    df = pd.DataFrame([_row("JNPPTBFR", 248576, 3000, 0, link=2500, outbound=1200),
                       _row("CATEDERPAS Remix", 12785, 200, 0, link=150, outbound=90)])
    assert _values(funnel_stages(df)) == [261361, 2650, 1290]


def test_a_partly_measured_stage_is_dropped_not_undercounted() -> None:
    df = pd.DataFrame([_row("a", 1000, 50, 0, link=40, outbound=20),
                       _row("b", 1000, 50, 0)])  # collected before migration 138
    stages = funnel_stages(df)
    assert _values(stages) == [2000, 100]
    assert "Clics sortants" not in _labels(stages)
