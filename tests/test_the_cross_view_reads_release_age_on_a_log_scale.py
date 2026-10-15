"""R567 — the cross view's « releases at equal age » reads its days on a log axis.

Type: Test
Uses: src.dashboard.views.spotify_s4a_combined (log_day_range), ast
Depends on: nothing — pure function + source read
Persists in: nothing

Owner, 2026-10-15: « échelle log centrée sur la fenêtre de dépense Meta ». The range is
centred on the paid days; the Spotify page keeps its linear axis (`log_days` defaults off).
"""
from __future__ import annotations

import ast
import math
from pathlib import Path

import pandas as pd

from src.dashboard.views.spotify_s4a_combined import log_day_range

_ROOT = Path(__file__).resolve().parents[1]


def test_the_range_is_centred_on_the_paid_days() -> None:
    meta = pd.DataFrame({"day_index": [10, 11, 30]})
    lo, hi = log_day_range(meta, horizon=400)
    assert math.isclose(lo, math.log10(10) - 0.5)
    assert math.isclose(hi, math.log10(30) + 0.5)


def test_without_spend_the_range_is_the_whole_horizon() -> None:
    assert log_day_range(pd.DataFrame(columns=["day_index"]), horizon=100) == [0.0, 2.0]


def test_the_range_never_leaves_the_measured_horizon() -> None:
    lo, hi = log_day_range(pd.DataFrame({"day_index": [1, 90]}), horizon=100)
    assert lo == 0.0 and hi == 2.0


def _log_days_by_caller() -> dict[str, object]:
    out = {}
    for name in ("meta_ads_overview.py", "spotify_s4a_combined.py"):
        tree = ast.parse((_ROOT / "src/dashboard/views" / name).read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "render_release_cohort":
                kw = {k.arg: k.value for k in n.keywords}
                out[name] = getattr(kw.get("log_days"), "value", False)
    return out


def test_only_the_cross_view_asks_for_the_log_axis() -> None:
    assert _log_days_by_caller() == {"meta_ads_overview.py": True,
                                     "spotify_s4a_combined.py": False}
