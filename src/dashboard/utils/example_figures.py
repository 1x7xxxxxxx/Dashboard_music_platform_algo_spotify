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

Each image carries « Exemple — données fictives » drawn into the pixels (see
`tools/dev/make_example_charts.py::_example_badge`) and the caption repeats it, so a
screenshot and a screen reader both say it. The two promise figures are generated at the
same pixel height so they sit level side by side.

ONE module so the algo preview shows the SAME prediction figure (V55: DW / RR / Radio had
no chart) instead of a second illustration that would drift from the first.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.dashboard.utils.i18n import t

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "assets" / "examples"

OVERVIEW = "dashboard-global.png"
ALGO_PREDICTION = "prediction-discover-weekly.png"
CAMPAIGN = "meta-x-s4a.png"
PROMISES = (ALGO_PREDICTION, CAMPAIGN)   # the order the owner asked for (V12)


def example_caption() -> str:
    return t("charts.example_caption", "Exemple — données fictives, à titre d'illustration")


def render_example(name: str) -> None:
    """Show one prebuilt example figure at the width of its container.

    Missing, it renders nothing: the sentence beside it already states the promise.
    """
    path = EXAMPLES_DIR / name
    if path.exists():
        st.image(str(path), caption=example_caption(), width="stretch")
