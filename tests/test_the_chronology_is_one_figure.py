"""R555 — the cross view draws every daily reading on ONE clock (owner Y2, 2026-10-13).

Fiches 42 (listener verdict), 43 (campaign journey in base 100) and 29 (spend, clicks,
CPR) drew the same days three times; fiche 6 (Shazam launches) a fourth. One figure now,
each series in its own `legendgroup` so the owner can « afficher ou non » from the legend.
"""
import ast
from pathlib import Path

import pandas as pd

from src.dashboard.utils import chronology

ROOT = Path(__file__).resolve().parent.parent


def _frames():
    days = pd.date_range("2026-08-01", periods=60)
    audience = pd.DataFrame({"day": days, "listeners": range(60), "streams": range(60),
                             "saves": range(60), "playlist_adds": range(60),
                             "followers_level": range(100, 160)})
    shazam = pd.DataFrame({"day": days[::5], "shazams": 3})
    meta = pd.DataFrame({"day": days[20:40], "spend": 5.0, "clicks": 4})
    all_spend = meta.assign(ad_account_id="a", campaign_name="c")[
        ["ad_account_id", "campaign_name", "day", "spend"]]
    return {"audience": audience, "shazam": shazam, "meta": meta, "all_spend": all_spend}


def test_every_reading_is_one_legend_group_of_one_figure():
    fig = chronology.figure(_frames())
    groups = [tr.legendgroup for tr in fig.data]
    assert len(groups) >= 8, groups
    assert all(groups) and len(set(groups)) == len(groups), groups


def test_the_budget_is_an_area_on_the_euro_axis():
    fig = chronology.figure(_frames())
    budget = next(tr for tr in fig.data if tr.legendgroup == "budget")
    assert budget.yaxis == "y2" and budget.fill == "tozeroy"
    assert fig.layout.yaxis2.overlaying == "y"


def test_nothing_measured_draws_nothing():
    assert chronology.figure({}) is None


def _defs(rel: str) -> set[str]:
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    return {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}


def test_the_four_separate_figures_are_gone():
    assert not {"_render_listener_verdict", "_render_chart"} & _defs(
        "src/dashboard/views/meta_x_spotify.py")
    assert "_show_meta_ads" not in _defs("src/dashboard/views/meta_ads_overview.py")
    assert "render_shazam_launches" not in _defs("src/dashboard/views/apple_music.py")
    assert "_render_timeline" in _defs("src/dashboard/views/meta_ads_overview.py")
