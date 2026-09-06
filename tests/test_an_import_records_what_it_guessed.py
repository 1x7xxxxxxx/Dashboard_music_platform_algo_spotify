"""Guard: ce qu'on a DEVINÉ doit être écrit, sur le refus comme sur le succès.

Type: Utility
Uses: ast, src.dashboard.views.upload_csv
Triggers: pytest
Persists in: nothing

Error class `a-guess-that-leaves-no-trace`.

« CSV file encoding and schema information must be configured in the target system
  to ensure appropriate ingestion. Autodetection is a convenience feature provided in
  many cloud environments but is **inappropriate for production ingestion**. As a
  best practice, engineers should **record CSV encoding and schema details** in file
  metadata. »
        — Reis & Housley, *Fundamentals of Data Engineering*, p. 374

On ne peut pas cesser de deviner : les fichiers viennent de Spotify, d'Apple et
parfois d'un Excel français, et rien ne nous laisse configurer la source. Ce que la
seconde phrase rend possible, c'est d'enregistrer la devinette — et c'est la moitié
qui manquait. Le 2026-09-06, douze exports ont été refusés à cause d'un BOM et rien,
nulle part, ne disait quel encodage avait gagné : l'écran affichait « Colonnes
vues : ﻿date, streams », où le BOM ne se rend pas.

La trace compte le PLUS sur le succès, et c'est précisément là qu'elle manquait :
un fichier lu avec le mauvais séparateur ne lève pas, il importe des chiffres faux
qu'on relira des semaines plus tard.
"""
from __future__ import annotations

import ast
import io
import pathlib

import pytest

from src.dashboard.views.upload_csv import _resolve_serialization, _serialization_label

_VIEW = pathlib.Path("src/dashboard/views/upload_csv.py")


def _upload(raw: bytes, name: str = "export.csv"):
    buf = io.BytesIO(raw)
    buf.name = name
    return buf


@pytest.mark.parametrize(
    "raw,expected_enc,expected_sep",
    [
        ("date,streams\n".encode("utf-8-sig"), "utf-8-sig", ","),
        (b"date;streams\n", "utf-8-sig", ";"),
        (b"date\tstreams\n", "utf-8-sig", "\t"),
        # Contenu NON-ASCII en cp1252 : `utf-8-sig` et `utf-8` échouent tous deux,
        # la résolution retombe donc réellement sur `latin-1`. Le premier jet de ce
        # cas encodait « date,titre » — de l'ASCII pur, lu par `utf-8-sig` : le test
        # s'appelait « cp1252 » et ne mesurait rien de cp1252.
        ("date,tîtré\n".encode("cp1252"), "latin-1", ","),
    ],
    ids=["bom", "excel-fr", "tab", "non-ascii-fallback"],
)
def test_the_resolution_reports_what_it_chose(raw, expected_enc, expected_sep):
    enc, sep, _line = _resolve_serialization(_upload(raw))
    assert (enc, sep) == (expected_enc, expected_sep), (
        "la résolution doit RENDRE l'encodage et le séparateur retenus ; les garder "
        "pour elle est ce qui a rendu le refus du 2026-09-06 indiagnosticable."
    )


def test_the_label_never_lies_about_a_binary():
    """`latin-1` décode n'importe quels octets — une trace fausse est pire qu'aucune."""
    label = _serialization_label(_upload(b"PK\x03\x04\x00\x00", name="relevé.xlsx"))
    assert "latin-1" not in label and "xlsx" in label, (
        f"un classeur Excel n'a ni encodage de texte ni séparateur, or le label dit "
        f"{label!r}"
    )


def _log_inserts() -> list[ast.Call]:
    """Tout appel qui écrit dans `csv_upload_log`, lu sur l'AST et non sur le texte."""
    tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        sql = node.args[0]
        text = ""
        if isinstance(sql, ast.Constant) and isinstance(sql.value, str):
            text = sql.value
        elif isinstance(sql, ast.JoinedStr):
            continue
        else:
            # concaténation implicite d'adjacents : ast la rend déjà en Constant,
            # mais une BinOp `"a" + "b"` reste à plier.
            try:
                text = ast.literal_eval(sql)
            except (ValueError, SyntaxError, TypeError):
                continue
        if isinstance(text, str) and "csv_upload_log" in text and "INSERT" in text:
            found.append(node)
    return found


@pytest.mark.parametrize("status", ["rejected", "success"])
def test_every_csv_log_insert_carries_the_serialization(status):
    inserts = _log_inserts()
    assert inserts, "aucune écriture dans csv_upload_log — garde à repointer"

    for call in inserts:
        sql = ast.literal_eval(call.args[0])
        if f"'{status}'" not in sql:
            continue
        assert "serialization" in sql, (
            f"l'écriture `{status}` n'enregistre pas la sérialisation retenue. "
            "Les colonnes vues disent ce qu'on a lu, jamais avec quel encodage ni "
            "quel séparateur — c'est exactement ce qui manquait le 2026-09-06."
        )
        break
    else:
        pytest.fail(f"aucune écriture de statut {status!r} dans csv_upload_log")
