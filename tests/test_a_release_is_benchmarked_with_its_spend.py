"""R271 (owner note L470) — « Mes sorties à âge égal » carries the Meta spend and the Shazams
of each release, day by day since release, each in its own panel.

Type: Test
Uses: src/dashboard/views/spotify_s4a_combined.py (worth_a_panel, _release_overlays)

Seen on the render (2026-09-28): two Apple readings at 0 drew a Shazam panel on a −1..1
axis. A panel appears only when one of its values is non-zero.

Mutation record (2026-09-28) : `worth_a_panel` answering True on an all-zero frame → red ;
the overlay query no longer bounded by the release horizon → red.
"""
import ast
from pathlib import Path

import pandas as pd

from src.dashboard.views.spotify_s4a_combined import worth_a_panel

ROOT = Path(__file__).resolve().parents[1]


def test_a_panel_of_zeros_is_not_drawn():
    assert not worth_a_panel(pd.DataFrame({"shazams": [0, 0]}), "shazams")
    assert not worth_a_panel(pd.DataFrame(), "shazams")
    assert worth_a_panel(pd.DataFrame({"spend": [0, 9.15]}), "spend")


def test_the_overlays_read_gold_and_stop_at_the_common_horizon():
    src = (ROOT / "src/dashboard/views/spotify_s4a_combined.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "_release_overlays")
    sql = " ".join(n.value for n in ast.walk(fn) if isinstance(n, ast.Constant)
                   and isinstance(n.value, str))
    assert "v_meta_daily" in sql and "v_apple_song_daily" in sql
    assert sql.count("BETWEEN 0 AND %s") == 2, "each overlay is cut at the compared horizon"
