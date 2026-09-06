"""Guard: un NaN pandas ne doit jamais devenir la chaîne « nan » en base.

Type: Utility
Uses: ast, pathlib, src.transformers.imusician_csv_parser
Triggers: pytest
Persists in: nothing

Error class `nan-written-as-a-value`.

`str(row[col] or '').strip() or None` était le motif employé dans tout le parseur
iMusician. Il paraît sûr et ne l'est pas : **un NaN pandas est VRAI** en contexte
booléen, donc `nan or ''` rend `nan`, et `str(nan)` rend la chaîne `'nan'`.

Mesuré en production le 2026-09-06 : 2 533 lignes de `track_version`, deux `isrc` et
deux `track_title` valant littéralement « nan ». Les requêtes `IS NULL` ne les
voient pas, les regroupements les comptent comme une valeur.

Le coût n'est pas cosmétique, et c'est ce qui l'a fait découvrir : l'ISRC est la clé
exacte du secteur — chaque version d'un morceau en porte une propre — et une absence
écrite `'nan'` regroupe sous UNE MÊME valeur tout ce qui n'a pas d'identifiant. Le
pire regroupement possible pour une colonne dont le rôle est de distinguer.

Le garde tient les deux moitiés : le comportement de `_text`, et l'absence du motif
fautif dans les parseurs — c'est un motif qu'on réécrit sans y penser.
"""
from __future__ import annotations

import pathlib
import re

import pytest

_TRANSFORMERS = pathlib.Path("src/transformers")

# La forme RÉELLE du défaut : une clé de dictionnaire alimentée par `str(...) or ''`.
# Volontairement ancrée sur `^\\s+'clé':` — une première version de cette recherche
# matchait la PROSE qui décrit le défaut (dans ce fichier et dans le catalogue),
# donc documenter le correctif faisait rougir la CI, et la seule façon de la garder
# verte aurait été d'arrêter d'écrire.
_OFFENDING = re.compile(r"^\s+'[a-z_]+':\s+str\(.*or ''\)\.strip\(\)")


def test_text_turns_a_nan_into_none():
    import pandas as pd

    from src.transformers.imusician_csv_parser import _text

    assert _text(float("nan")) is None, (
        "un NaN est VRAI en booléen : `nan or ''` rend `nan`, et `str(nan)` rend "
        "la chaîne 'nan'. C'est tout le défaut.")
    assert _text(pd.NA) is None
    assert _text(None) is None
    assert _text("") is None
    assert _text("   ") is None
    assert _text("  FR9W12411305 ") == "FR9W12411305"
    assert _text(0) == "0", "un zéro est une valeur, pas une absence"


@pytest.mark.parametrize(
    "path", sorted(_TRANSFORMERS.rglob("*.py")),
    ids=lambda p: p.name)
def test_no_parser_builds_a_value_with_str_or_empty(path):
    offenders = [
        f"{path}:{i}" for i, line in
        enumerate(path.read_text(encoding="utf-8").split("\n"), 1)
        if _OFFENDING.match(line)
    ]
    assert not offenders, (
        f"{', '.join(offenders)} : `str(x or '')` écrit 'nan' quand `x` est un NaN "
        "pandas, parce qu'un NaN est VRAI en booléen. Utilise `_text(x)`, qui teste "
        "`pd.isna` AVANT toute évaluation booléenne.")


def test_the_cleanup_migration_is_still_there():
    """Le correctif du code ne répare pas les lignes déjà écrites."""
    sql = pathlib.Path("migrations/092_nan_is_not_a_value.sql")
    assert sql.exists(), "la migration de nettoyage a disparu"
    body = sql.read_text(encoding="utf-8")
    for column in ("isrc", "track_title", "track_version"):
        assert f"SET {column}" in body, (
            f"`{column}` n'est plus nettoyée — c'est pourtant une colonne sur "
            "laquelle `track_release_reference` s'appuie désormais.")
