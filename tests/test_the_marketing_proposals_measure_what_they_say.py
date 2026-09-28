"""The R282 proposals compute what their titles claim (tools/dev/charts_dossier/proposals.py).

A proposal is judged by the owner on its picture; the calculations under the pictures are
pinned here on series whose answer is known by construction. The lag, CTA, fatigue and
playlist proposals were refused by the owner on 2026-09-28 and removed with their tests;
P2 lives in the app (R291, tests/test_a_campaign_wave_is_judged_as_one.py); B and D since
R301 (tests/test_the_r282_figures_live_in_the_app.py, which now pins `event_study`).

Does not cover: the SQL (it runs on the review snapshot only), nor the drawing — the PNGs are
looked at before the dossier is sent.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "dev" / "charts_dossier"))

import proposals  # noqa: E402



def test_streams_per_click_is_none_when_nothing_was_gained():
    assert proposals.streams_per_click(500.0, 250.0) == 2.0
    assert proposals.streams_per_click(None, 250.0) is None
    assert proposals.streams_per_click(-10.0, 250.0) is None
