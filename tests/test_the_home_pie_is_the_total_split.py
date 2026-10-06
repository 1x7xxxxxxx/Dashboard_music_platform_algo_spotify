"""The home pie splits THE total shown above it, and the tile rows follow V3 (R371).

Type: Guard
Uses: src.dashboard.views.home_tiles, src.dashboard.utils.platform_share
Persists in: nothing

A pie computed on its own would be a second total — the home page already paid for
three totals on three pages. Its slices must sum to the banner's number, and an
absent platform must be left out, never drawn as a zero.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.dashboard.utils.platform_share import platform_share_figure
from src.dashboard.utils.platform_timeseries import combined_total

_FULL = {"spotify": 1000, "youtube": 900, "apple": 800, "soundcloud": 700}


def _render(totals: dict, side: dict, ig: int):
    from streamlit.testing.v1 import AppTest

    root = str(Path(__file__).resolve().parents[1])
    at = AppTest.from_string(
        f"import sys; sys.path.insert(0, {root!r})\n"
        "from src.dashboard.views.home_tiles import render_tiles\n"
        "from src.dashboard.utils.platform_timeseries import combined_total\n"
        f"render_tiles({totals!r}, combined_total({totals!r}), {ig}, side={side!r})\n")
    at.run(timeout=90)
    assert not at.exception, f"render raised: {at.exception}"
    return at


def test_the_pie_has_four_slices_summing_to_the_total() -> None:
    at = _render(_FULL, {}, 0)
    charts = at.get("plotly_chart")
    assert len(charts) == 1, f"expected one pie on the KPI column, got {len(charts)}"
    spec = json.loads(charts[0].proto.spec)
    pie = spec["data"][0]
    assert pie["type"] == "pie"
    assert len(pie["values"]) == 4
    assert sum(pie["values"]) == combined_total(_FULL), (
        "the slices do not sum to the total shown above them — a second total")


def test_an_absent_platform_is_not_a_slice() -> None:
    fig = platform_share_figure({"spotify": 10, "youtube": None, "apple": 0,
                                 "soundcloud": 5})
    assert list(fig.data[0].labels) == ["Spotify", "SoundCloud"]
    assert platform_share_figure({"spotify": 10}) is None, "one slice is not a share"


def test_meta_hypeddit_come_before_shazam_instagram() -> None:
    side = {"shazam_total": 5, "meta_spend": 6.0, "hypeddit_ctr": 7.0}
    labels = [m.label for m in _render(_FULL, side, 8).metric]
    order = [labels.index(x) for x in
             ("📊 Meta Ads", "📱 Hypeddit", "🎧 Shazam", "📸 Instagram")]
    assert order == sorted(order) and order[1] == order[0] + 1 \
        and order[3] == order[2] + 1, f"V3 row order lost: {labels}"


# R421 (2026-10-06): the gates' caption is gone; « maximale » now lives in each gate's
# tooltip — guarded in tests/test_a_recap_row_answers_the_question_it_names.py.
