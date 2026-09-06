"""Guard: a byte-order mark must never make a valid export unrecognisable.

Type: Utility
Uses: io, src.dashboard.views.upload_csv
Triggers: pytest
Persists in: nothing

Error class `bom-survives-the-encoding-fallback`.

Measured 2026-09-06 on a real import: TWELVE Spotify for Artists files out of
fourteen refused as « type non reconnu ». Spotify writes its CSV exports with a
UTF-8 BOM; Excel adds one too when a French-locale user re-saves a file.

Two things had to be true at once, and both were:

* `_read_headers` tried `'utf-8'` BEFORE `'utf-8-sig'`. A UTF-8 file carrying a BOM
  decodes without error as `utf-8`, so the loop stopped at the first attempt and the
  BOM survived, glued to the first header: `\\ufeffdate` instead of `date`;
* `str.strip()` does not remove `\\ufeff` — it is not whitespace — so the column
  normalisation in `_detect_platform` left it in place.

What made it expensive is that the error message was RIGHT and unreadable: « Colonnes
vues : ﻿date, streams » shows the correct column name, because the BOM renders as
nothing. Nobody could see the difference between the header we had and the header we
wanted.
"""
from __future__ import annotations

import io

import pytest

from src.dashboard.views.upload_csv import _detect_platform, _read_headers

# Les fichiers RÉELS du rapport du 2026-09-06, avec leurs colonnes exactes.
_CASES = [
    ("Kimono à semelle de fer-timeline.csv", "date,streams", "s4a"),
    ("Ô Chiotte l'arbitre Tucome Back - Original-timeline.csv", "date,streams", "s4a"),
    ("Qui a sali mon slip avec de la gadoue_-timeline.csv", "date,streams", "s4a"),
    ("1x7xxxxxxx-audience-timeline.csv",
     "date,listeners,monthly listeners,monthly active listeners,super listeners,"
     "streams,playlist adds,saves,followers", "s4a_audience"),
    ("1x7xxxxxxx-songs-1year.csv",
     "song,listeners,streams,saves,release_date", "s4a_songs_global"),
]

# Les trois façons dont le même fichier peut arriver. `utf-8-sig` produit les mêmes
# octets que `utf-8` avec BOM — c'est le point : rien dans le contenu ne distingue
# « fichier fautif » de « fichier normal », seul le préfixe change.
_PREFIXES = {"sans BOM": b"", "avec BOM": b"\xef\xbb\xbf"}


class _Upload(io.BytesIO):
    """Ce que Streamlit passe : un flux binaire qui porte un `.name`."""

    def __init__(self, name: str, data: bytes) -> None:
        super().__init__(data)
        self.name = name


def _build(name: str, header: str, prefix: bytes) -> _Upload:
    row = "\n2026-01-01," + ",".join(["1"] * header.count(",")) + "\n"
    return _Upload(name, prefix + (header + row).encode("utf-8"))


@pytest.mark.parametrize("label,prefix", _PREFIXES.items(), ids=list(_PREFIXES))
@pytest.mark.parametrize("name,header,expected", _CASES,
                         ids=[c[2] + ":" + c[0][:18] for c in _CASES])
def test_the_same_export_is_recognised_with_or_without_a_bom(
        label, prefix, name, header, expected):
    """La question : le préfixe invisible change-t-il la réponse ? Il ne doit pas."""
    got = _detect_platform(name, _read_headers(_build(name, header, prefix)))
    assert got == expected, (
        f"{name} ({label}) → {got!r} au lieu de {expected!r}. Un octet invisible en "
        "tête de fichier suffit à faire refuser un export valide, et le message "
        "d'erreur affiche la BONNE colonne — le BOM ne se rend pas.")


def test_the_header_reader_strips_the_mark_at_the_source():
    """Première couche : plus aucun en-tête ne sort d'ici avec un BOM."""
    headers = _read_headers(_build("x-timeline.csv", "date,streams", b"\xef\xbb\xbf"))
    assert headers, "aucun en-tête lu"
    assert not any(h.startswith("﻿") for h in headers), (
        f"le BOM survit à la lecture : {headers!r}. `utf-8-sig` doit être essayé "
        "AVANT `utf-8`, qui décode un fichier BOMé sans erreur et le conserve.")


@pytest.mark.parametrize("form", ["﻿", "ï»¿"])
def test_the_column_normaliser_is_the_second_layer(form):
    """Seconde couche : un en-tête BOMé venu d'ailleurs se compare quand même.

    `\\ufeff` n'est pas un blanc, donc `strip()` ne suffit pas ; `ï»¿` est le même
    octet-pour-octet lu en latin-1. Les deux doivent disparaître avant comparaison.
    """
    got = _detect_platform("x-timeline.csv", [form + "date", "streams"])
    assert got == "s4a", (
        f"un en-tête préfixé de {form!r} n'est pas normalisé : la détection échoue "
        "sur une colonne qui s'AFFICHE correctement")
