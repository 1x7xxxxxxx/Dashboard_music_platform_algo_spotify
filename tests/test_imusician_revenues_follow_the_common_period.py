"""R478 — iMusician revenues follow the app's common period, by whole months.

Type: Test
Uses: src/dashboard/views/imusician.py (months_in_window)

Before R478 the page filtered by « année » / « mois » multiselects — another selector
than everywhere else (W11 : « mêmes filtres cohérents dans toute l'app »). Revenues are
MONTHLY : a window starting mid-month must keep that month, not drop it.
"""
from datetime import date

import pandas as pd

from src.dashboard.views.imusician import months_in_window


def test_a_window_starting_mid_month_keeps_that_month():
    starts = pd.Series(pd.to_datetime(["2026-08-01", "2026-09-01", "2026-10-01"]))
    kept = months_in_window(starts, date(2026, 9, 17), date(2026, 10, 9))
    assert kept.tolist() == [False, True, True]


def test_the_whole_history_keeps_every_month():
    starts = pd.Series(pd.to_datetime(["2024-01-01", "2026-10-01"]))
    assert months_in_window(starts, date(2024, 1, 1), date(2026, 10, 9)).all()
