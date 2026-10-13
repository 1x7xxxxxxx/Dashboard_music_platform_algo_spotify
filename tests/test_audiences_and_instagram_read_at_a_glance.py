"""R558 — audiences and Instagram read at a glance (owner's notes of 2026-10-13).

Fiche 33: comments and shares were measured but a pixel wide beside the reactions —
each column of the engagement grid now has its own scale and its count written.
Fiche 45: countries ranked by € per listen, cheapest first.
Fiches 18-19: the Meta spend drawn as an area behind the Instagram curves.
"""
import pandas as pd
import pytest

from src.dashboard.utils import engagement_grid, meta_spend_overlay
from src.dashboard.views.meta_x_spotify import countries_order


def _part():
    return pd.DataFrame({"dim_label": ["18-24", "25-34"],
                         "reactions": [12000, 248], "comments": [3, 36]})


def test_each_column_is_shaded_on_its_own_maximum():
    shade = engagement_grid.column_shade(_part()[["reactions", "comments"]])
    # 36 comments are as dark as 12 000 reactions: each is its column's maximum.
    assert shade["reactions"].tolist()[0] == 1.0 and shade["comments"].tolist()[1] == 1.0
    assert shade["comments"].tolist()[0] == pytest.approx(3 / 36)


def test_an_all_zero_column_is_blank_not_nan():
    shade = engagement_grid.column_shade(pd.DataFrame({"shares": [0, 0]}))
    assert shade["shares"].tolist() == [0.0, 0.0]


def test_the_count_is_written_in_every_cell():
    cells = [c for row in engagement_grid.cell_text(_part()[["reactions", "comments"]])
             for c in row]
    assert len(cells) == 4 and any("36" in c for c in cells)
    assert "**36** Commentaires" == engagement_grid.totals_line(
        pd.DataFrame({"comments": [30, 6]}), {"comments": "Commentaires"})


def test_no_spend_draws_no_area():
    assert meta_spend_overlay.area_trace(pd.DataFrame(columns=["x", "spend"])) is None
    assert meta_spend_overlay.area_trace(pd.DataFrame({"x": [1], "spend": [0.0]})) is None
    tr = meta_spend_overlay.area_trace(pd.DataFrame({"x": [1], "spend": [12.0]}))
    assert tr.fill == "tozeroy"


class _Window:
    def sql_between(self, col):
        return f" AND {col} BETWEEN %s AND %s ", ("2026-01-01", "2026-02-01")


class _Db:
    def __init__(self):
        self.calls = []

    def fetch_df(self, q, params):
        self.calls.append((q, params))
        return pd.DataFrame({"x": ["2026-01-02", "2026-01-03"], "spend": [5, 0]})


def test_the_spend_is_read_inside_the_page_window_and_zero_days_dropped():
    db = _Db()
    out = meta_spend_overlay.spend_by(db, 7, _Window(), grain="month")
    q, params = db.calls[0]
    assert "BETWEEN" in q and params == (7, "2026-01-01", "2026-02-01")
    assert len(out) == 1
    with pytest.raises(ValueError):
        meta_spend_overlay.spend_by(db, 7, _Window(), grain="week")


def test_countries_are_ranked_cheapest_listen_first_among_the_most_spent():
    meta = pd.DataFrame({"pays": ["MX", "CO", "FR", "XX"],
                         "spend": [844.0, 110.0, 60.0, 1.0],
                         "cout_par_ecoute": [0.027, 0.002, None, 0.0001]})
    assert countries_order(meta, top=3)["pays"].tolist() == ["CO", "MX", "FR"]
