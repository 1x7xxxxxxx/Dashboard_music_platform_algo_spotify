"""Guard: un export Apple dit quelle période il couvre, et on ne l'additionne pas mal.

Type: Utility
Uses: src.dashboard.utils.platform_timeseries, src.dashboard.views.upload_csv
Triggers: pytest
Persists in: nothing

Error class `two-shapes-summed-as-one`.

Question posée le 2026-09-08 : « y a-t-il un intérêt de demander à l'artiste d'importer
les CSV de chaque année pour nos graphiques Apple Music ? »

Oui — et la réponse tient à un fait qui décide de tout : **l'export Apple n'a aucune
colonne de date**. C'est le sélecteur de leur interface qui choisit la période, et le
fichier n'en garde pas la trace. Trois conséquences, chacune gardée ici :

1. sans question, trois exports annuels déposés le même jour s'écrasent (même clé) ;
2. deux exports annuels sont des périodes **disjointes** — les soustraire l'un de
   l'autre comme deux photos d'un cumul n'a aucun sens ;
3. un cumul « depuis le début » CONTIENT déjà les années : les additionner compte les
   mêmes écoutes deux fois.

C'est la même faute que celle du matin — additionner deux grandeurs différentes — sur
une autre table.
"""
from __future__ import annotations

import ast
import datetime as dt
import pathlib

import pytest

from src.dashboard.utils import platform_timeseries as pts

_UPLOAD = pathlib.Path("src/dashboard/views/upload_csv.py")


class _DB:
    """Répond selon la FORME demandée : bornée, ou cumul. Un stub uniforme ne verrait
    pas l'écart que ce fichier teste."""

    def __init__(self, bounded=0, lifetime_rows=None, last_lifetime=None):
        self.bounded, self.lifetime_rows = bounded, lifetime_rows or []
        self.last_lifetime = last_lifetime
        self.asked: list = []

    def fetch_query(self, sql, params=None):  # noqa: ANN001
        self.asked.append(sql)
        if "period_start IS NOT NULL" in sql and "SUM(plays)" in sql:
            return [(self.bounded,)]
        if "MAX(snapshot_date)" in sql:
            return [(self.last_lifetime or 0,)]
        if "period_start IS NULL" in sql and "GROUP BY" in sql:
            return self.lifetime_rows
        if "period_start IS NULL" in sql:
            return [(self.last_lifetime or 0,)]
        return [(0,)]


def test_the_period_is_asked_because_the_file_cannot_say_it() -> None:
    """Le parseur REFUSE de deviner : il lève la question, il ne choisit pas.

    Lu sur la structure : ce fichier nomme `apple_period` dans sa documentation.
    """
    tree = ast.parse(_UPLOAD.read_text(encoding="utf-8"))
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == "_parse_file")
    raises = [n for n in ast.walk(fn) if isinstance(n, ast.Raise)]
    asks = [n for n in raises
            if "MissingFromFilenameError" in (ast.unparse(n) or "")
            and "apple_period" in (ast.unparse(n) or "")]
    assert asks, (
        "l'import Apple ne demande plus sa période : elle sera devinée, et trois "
        "exports annuels déposés le même jour s'écraseront")

    # ET la question doit pouvoir se poser : un repli sur une valeur par défaut la
    # rendrait inatteignable tout en laissant le `raise` en place. Mesuré — c'est
    # exactement la mutation qui laissait ce garde vert.
    reads = [n for n in ast.walk(fn)
             if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "get"
             and n.args and isinstance(n.args[0], ast.Constant)
             and n.args[0].value == "apple_period"]
    assert reads, "la réponse `apple_period` n'est plus lue — garde à repointer"
    for call in reads:
        assert len(call.args) == 1, (
            "la lecture de la période porte une valeur par défaut : la question ne "
            "sera jamais posée, et la période sera devinue")
        parent = next((b for b in ast.walk(fn)
                       if isinstance(b, ast.BoolOp) and call in ast.walk(b)), None)
        if parent is not None:
            assert all(isinstance(v, ast.Constant) is False or v.value == ""
                       for v in parent.values[1:]), (
                "le `or` qui suit la lecture porte une période par défaut — même "
                "effet qu'un défaut dans le `get`")


@pytest.mark.parametrize("period,expected", [
    ("all", (None, None)),
    ("2024", (dt.date(2024, 1, 1), dt.date(2024, 12, 31))),
    ("", (None, None)),
])
def test_a_year_is_bounded_at_both_ends(period, expected) -> None:
    """Une année a un début ET une fin : c'est ce qui la place dans une fenêtre."""
    from src.dashboard.views.upload_csv import _apple_period_bounds
    assert _apple_period_bounds(period) == expected


def test_bounded_periods_are_summed_and_never_subtracted() -> None:
    """2023 + 2024 = les deux. Les soustraire serait traiter deux périodes comme un cumul."""
    db = _DB(bounded=1500)
    assert pts.apple_period_plays(db, 1, dt.date(2023, 1, 1), dt.date(2024, 12, 31)) == 1500


def test_lifetime_readings_are_subtracted_and_never_summed() -> None:
    """Deux cumuls se comparent. Les additionner compterait tout deux fois."""
    db = _DB(bounded=0, lifetime_rows=[(dt.date(2026, 1, 1), 3000),
                                       (dt.date(2026, 6, 1), 3400)])
    assert pts.apple_period_plays(db, 1) == 400


def test_a_single_lifetime_reading_yields_nothing() -> None:
    """Un écart a besoin de deux points ; « +0 » serait une affirmation non mesurée."""
    db = _DB(bounded=0, lifetime_rows=[(dt.date(2026, 1, 1), 3000)])
    assert pts.apple_period_plays(db, 1) is None


def test_the_lifetime_total_prefers_the_cumulative_reading() -> None:
    """Un cumul CONTIENT déjà les années : on ne lui ajoute pas ce qu'il porte."""
    db = _DB(bounded=1500, last_lifetime=3718)
    assert pts.apple_lifetime_plays(db, 1) == 3718, (
        "le total additionne le cumul ET les périodes qu'il contient — les mêmes "
        "écoutes comptées deux fois")


def test_without_a_cumulative_reading_the_years_are_summed() -> None:
    """Un artiste qui n'a déposé QUE des années a bien un total : la somme."""
    db = _DB(bounded=1500, last_lifetime=0)
    assert pts.apple_lifetime_plays(db, 1) == 1500
