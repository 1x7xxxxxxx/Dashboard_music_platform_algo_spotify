"""R578 — a creative is named by its place in Meta's hierarchy: campagne › ad set › pub.

Type: Guard
Uses: src/dashboard/views/meta_creatives.py (_pareto_frame)
Depends on: nothing (pure frame)
Persists in: nothing

Owner, 2026-10-15: make « campagne → ad set → pub » explicit. « créa · adset · campagne »
read right to left against Ads Manager's own order.
"""
from __future__ import annotations

import pandas as pd

from src.dashboard.views.meta_creatives import _pareto_frame


def test_the_label_reads_campaign_then_adset_then_ad() -> None:
    df = pd.DataFrame({"creative_name": ["clip", "photo"], "campaign_name": ["Été", "Été"],
                       "total_spend": [10.0, 30.0], "cpr": [0.1, 0.2]})
    adsets = pd.DataFrame({"creative_name": ["clip"], "campaign_name": ["Été"],
                           "adset_name": ["FR 18-24"]})
    labels = _pareto_frame(df, adsets)["label"].tolist()
    assert labels == ["Été › — › photo", "Été › FR 18-24 › clip"]
