"""The example figures — one generic overview and the two promises, never tenant data.

Type: Utility
Uses: src/dashboard/assets/examples/*.png (built offline by `make example-charts`), i18n
Triggers: views/onboarding.py (« 1. streaMLytics en bref »), views/algo_preview.py
Persists in: nothing

R374 (2026-10-05, owner's screen review V11, V12, V55). R347 had removed the welcome
block's figures because the first one was drawn from the tenant's data — with its
platform legend, its decision sentence and its period comparison. The owner wants a
figure back, but a GENERIC one, always available: a new tenant has no data, and the
figure must say what the tool does, not what it has collected so far.

R480 (2026-10-09, W3) : no « Exemple — données fictives » any more, neither in the pixels
nor as a caption — the owner's call. The figures are shown only where the sentence beside
them presents what the tool will show. The two promise figures are generated at the same
pixel height so they sit level side by side.

ONE module so the algo preview shows the SAME prediction figure (V55: DW / RR / Radio had
no chart) instead of a second illustration that would drift from the first.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "assets" / "examples"

OVERVIEW = "dashboard-global.png"
ALGO_PREDICTION = "prediction-discover-weekly.png"
CAMPAIGN = "meta-x-s4a.png"
PROMISES = (ALGO_PREDICTION, CAMPAIGN)   # the order the owner asked for (V12)
SHAP_OVERVIEW = "shap-overview.png"
# R456 (C8, C10): the free Road to Algo preview shows the two promises, then the SHAP
# overview — every figure an example, never the tenant's data.
ALGO_PREVIEW = (ALGO_PREDICTION, CAMPAIGN, SHAP_OVERVIEW)


def render_example(name: str) -> None:
    """Show one prebuilt example figure at the width of its container.

    Missing, it renders nothing: the sentence beside it already states the promise.
    """
    path = EXAMPLES_DIR / name
    if path.exists():
        st.image(str(path), width="stretch")
