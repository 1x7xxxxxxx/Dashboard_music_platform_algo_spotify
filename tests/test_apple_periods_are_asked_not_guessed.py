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
    """Répond selon la FORME demandée : relevés bornés, ou cumuls. Un stub uniforme ne
    verrait pas l'écart que ce fichier teste."""

    def __init__(self, readings=None, lifetime_rows=None, last_lifetime=None):
        self.readings = readings or []          # [(début, fin, écoutes)]
        self.lifetime_rows = lifetime_rows or []
        self.last_lifetime = last_lifetime

    def fetch_query(self, sql, params=None):  # noqa: ANN001
        if "period_start IS NOT NULL" in sql and "GROUP BY 1, 2" in sql:
            return list(self.readings)
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
    db = _DB(readings=[(dt.date(2023, 1, 1), dt.date(2023, 12, 31), 600),
                       (dt.date(2024, 1, 1), dt.date(2024, 12, 31), 900)])
    assert pts.apple_period_plays(db, 1, dt.date(2023, 1, 1), dt.date(2024, 12, 31)) == 1500


def test_nested_periods_are_never_counted_twice() -> None:
    """Le cas que la lecture automatique du nom de fichier CRÉE.

    Apple écrit ses bornes dans le nom (`songs_…_2015-06-30_2026-09-04.csv`), donc un
    artiste aura naturellement l'export « depuis le début » ET celui de 2024. Les
    additionner compterait 2024 deux fois — une fois seul, une fois dans le cumul.
    """
    readings = [(dt.date(2015, 6, 30), dt.date(2026, 9, 4), 3718),
                (dt.date(2024, 1, 1), dt.date(2024, 12, 31), 900)]
    cover = pts.non_overlapping_cover(readings)
    assert cover == [(dt.date(2024, 1, 1), dt.date(2024, 12, 31), 900)], (
        f"le découpage retenu se chevauche : {cover}")

    db = _DB(readings=readings)
    assert pts.apple_lifetime_plays(db, 1) == 3718, (
        "le total additionne le cumul et l'année qu'il contient")


def test_the_finest_slicing_wins_when_nothing_overlaps() -> None:
    """Trois années disjointes : les trois comptent, aucune n'est perdue."""
    readings = [(dt.date(2023, 1, 1), dt.date(2023, 12, 31), 600),
                (dt.date(2024, 1, 1), dt.date(2024, 12, 31), 900),
                (dt.date(2025, 1, 1), dt.date(2025, 12, 31), 400)]
    assert sum(p for _s, _e, p in pts.non_overlapping_cover(readings)) == 1900


def test_lifetime_readings_are_subtracted_and_never_summed() -> None:
    """Deux cumuls SANS bornes connues se comparent. Les additionner compterait double."""
    db = _DB(lifetime_rows=[(dt.date(2026, 1, 1), 3000),
                            (dt.date(2026, 6, 1), 3400)])
    assert pts.apple_period_plays(db, 1) == 400


def test_a_single_lifetime_reading_yields_nothing() -> None:
    """Un écart a besoin de deux points ; « +0 » serait une affirmation non mesurée."""
    db = _DB(lifetime_rows=[(dt.date(2026, 1, 1), 3000)])
    assert pts.apple_period_plays(db, 1) is None


def test_without_a_cumulative_reading_the_years_are_summed() -> None:
    """Un artiste qui n'a déposé QUE des années a bien un total : leur somme."""
    db = _DB(readings=[(dt.date(2023, 1, 1), dt.date(2023, 12, 31), 600),
                       (dt.date(2024, 1, 1), dt.date(2024, 12, 31), 900)])
    assert pts.apple_lifetime_plays(db, 1) == 1500


@pytest.mark.parametrize("filename,expected", [
    ("songs_1700256678_2015-06-30_2026-09-04.csv",
     (dt.date(2015, 6, 30), dt.date(2026, 9, 4))),
    ("songs_170_2024-01-01_2024-12-31.csv",
     (dt.date(2024, 1, 1), dt.date(2024, 12, 31))),
    ("songs (1).csv", None),          # renommé par le navigateur
    ("songs_2024-01-01.csv", None),   # une seule date ne fait pas une période
])
def test_the_period_is_read_from_the_filename(filename, expected) -> None:
    """Apple ÉCRIT ses bornes dans le nom — vérifié sur les dépôts réels.

    `songs_1700256678_2015-06-30_2026-09-04.csv`, lu dans `csv_upload_log` le
    2026-09-08. Ce sont les bornes EXACTES de l'export, pas seulement l'année : les
    lire évite de poser une question dont la réponse est déjà là.
    """
    from src.dashboard.views.upload_csv import _apple_period_from_filename
    assert _apple_period_from_filename(filename) == expected


def test_the_parser_actually_uses_the_filename_reader() -> None:
    """La lecture doit être BRANCHÉE, pas seulement correcte.

    Mesuré : remplacer l'appel par `bounds = None` laissait tous les autres tests
    verts — la fonction marchait, et plus personne ne l'appelait. C'est la classe
    `correct-code-nothing-reaches`, à l'échelle d'une ligne.
    """
    tree = ast.parse(_UPLOAD.read_text(encoding="utf-8"))
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == "_parse_file")
    called = {getattr(n.func, "id", "") for n in ast.walk(fn)
              if isinstance(n, ast.Call)}
    assert "_apple_period_from_filename" in called, (
        "`_parse_file` ne lit plus les dates du nom de fichier : la question sera "
        "posée à chaque dépôt alors que la réponse est écrite dessus")


def test_apple_is_a_yearly_point_never_spread_over_days() -> None:
    """Un export « 2024 » vaut UN point au 1ᵉʳ janvier, pas 366 valeurs quotidiennes.

    C'est la condition pour qu'Apple figure sur la même figure que les autres sans
    inventer : étaler 900 écoutes sur une année produirait 2,46 écoutes/jour que
    personne n'a mesurées.
    """
    db = _DB(readings=[(dt.date(2023, 1, 1), dt.date(2023, 12, 31), 600),
                       (dt.date(2024, 1, 1), dt.date(2024, 12, 31), 900)])
    assert pts.apple_yearly_series(db, 1) == [
        (dt.date(2023, 1, 1), 600), (dt.date(2024, 1, 1), 900)]


def test_a_multi_year_reading_never_joins_the_yearly_series() -> None:
    """L'export « depuis le début » couvre 2015→2026 : il recouvrirait chaque année."""
    db = _DB(readings=[(dt.date(2015, 6, 30), dt.date(2026, 9, 4), 3718),
                       (dt.date(2024, 1, 1), dt.date(2024, 12, 31), 900)])
    assert pts.apple_yearly_series(db, 1) == [(dt.date(2024, 1, 1), 900)], (
        "un relevé à cheval sur plusieurs années est entré dans la série annuelle : "
        "il compterait les années qu'il contient une seconde fois")

    # LE CAS QUI DISTINGUE VRAIMENT LES DEUX RÈGLES, et qu'il fallait ajouter : SEUL
    # l'export « depuis le début ». Le découpage non chevauchant le garde — il ne
    # chevauche rien — et sans le filtre sur l'année il deviendrait un point « 2015 »
    # portant onze ans d'écoutes. Mesuré : la première version de ce garde restait
    # verte quand on retirait le filtre.
    only_wide = _DB(readings=[(dt.date(2015, 6, 30), dt.date(2026, 9, 4), 3718)])
    assert pts.apple_yearly_series(only_wide, 1) == [], (
        "un relevé de onze ans est devenu un point « 2015 » : la figure annoncerait "
        "3 718 écoutes sur une année qui n'en a jamais vu autant")
