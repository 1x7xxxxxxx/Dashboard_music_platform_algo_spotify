"""Guard: la reconnaissance s'arrête à la détection — l'import va jusqu'aux lignes.

Type: Utility
Uses: io, src.dashboard.views.upload_csv, src.transformers.s4a_csv_parser
Triggers: pytest
Persists in: nothing

Error class `filename-dependency-survives-below-detection`.

Le 2026-09-06, « tous les fichiers, peu importe leur nom, doivent être reconnus » a
été tenu **à la détection** : `_detect_platform` ne lit plus que les colonnes. Le
garde qui le vérifie (`test_a_csv_is_recognised_whatever_its_encoding.py`) s'arrête
là — et deux couches plus bas, deux dépendances au nom de fichier étaient intactes :

* `parse_timeline` prenait le titre du morceau dans le nom et rendait `[]` sinon,
  affiché « Aucune ligne valide détectée après parsing » — un message qui accuse le
  CONTENU alors que le contenu est bon ;
* `_detect_window` **levait** si le nom ne portait ni `28d` ni `12m`, en conseillant
  de RENOMMER le fichier, c'est-à-dire de fabriquer à la main la donnée manquante.

Un fichier détecté qui rend zéro ligne est un fichier non importé. Ce garde mesure
donc la chaîne complète : détection → lecture → LIGNES, sur des noms neutralisés.

Il vérifie aussi la forme du refus restant. Le titre et la fenêtre ne sont dans
AUCUNE donnée — Spotify ne les met que dans le nom — donc ils ne peuvent pas être
devinés. La seule issue honnête est de les demander : l'exception porte alors un
`field` que la vue sait transformer en champ, et répondre doit produire les lignes.
"""
from __future__ import annotations

import io

import pandas as pd
import pytest

from src.dashboard.views.upload_csv import _detect_platform, _parse_file, _read_headers
from src.transformers.s4a_csv_parser import MissingFromFilenameError

_ARTIST = 7

# Contenu réel, nom NEUTRALISÉ : ni titre, ni période, ni jeton de type.
_CASES = [
    (
        "s4a",
        "date,streams\n2026-01-01,120\n2026-01-02,131\n",
        {"song": "Kimono à semelle de fer"},
    ),
    (
        "s4a_audience",
        "date,listeners,streams,followers\n2026-01-01,10,120,3\n",
        {},
    ),
    (
        "s4a_songs_global",
        "song,listeners,streams,saves,release_date\n"
        "Kimono,10,120,4,2025-04-01\n",
        {"window": "12m"},
    ),
]


def _upload(content: str, name: str = "export.csv"):
    buf = io.BytesIO(content.encode("utf-8-sig"))  # BOM inclus, comme Spotify
    buf.name = name
    return buf


@pytest.mark.parametrize("expected_key,content,answers", _CASES,
                         ids=[c[0] for c in _CASES])
def test_a_neutral_filename_still_produces_rows(expected_key, content, answers):
    f = _upload(content)
    key = _detect_platform(f.name, _read_headers(f))
    assert key == expected_key, (
        f"`export.csv` portant {content.splitlines()[0]!r} devrait être détecté "
        f"{expected_key!r}, pas {key!r} — la détection ne doit rien devoir au nom."
    )

    f.seek(0)
    rows = _parse_file(key, f, _ARTIST, answers)
    assert rows, (
        f"{expected_key} : détecté puis ZÉRO ligne. Un fichier reconnu qui n'importe "
        "rien n'est pas reconnu — la dépendance au nom a seulement changé de couche."
    )
    assert all(r.get("artist_id") == _ARTIST for r in rows), (
        "toute ligne écrite nomme son locataire (règle transverse)"
    )


def test_a_missing_title_is_a_question_not_a_dead_end():
    """Sans titre lisible, on DEMANDE — on ne rend pas une liste vide."""
    from src.transformers.s4a_csv_parser import S4ACSVParser

    df = pd.DataFrame({"date": ["2026-01-01"], "streams": [12]})
    with pytest.raises(MissingFromFilenameError) as exc:
        S4ACSVParser().parse_timeline(df, artist_id=_ARTIST, filename="")
    assert exc.value.field == "song", (
        "la vue s'appuie sur `field` pour choisir le champ à afficher"
    )

    rows = S4ACSVParser().parse_timeline(
        df, artist_id=_ARTIST, filename="", song_name="Kimono")
    assert rows and rows[0]["song"] == "Kimono", (
        "répondre à la question doit produire les lignes ; sinon le champ affiché "
        "par la vue ne mène nulle part"
    )


def test_a_missing_window_never_advises_a_rename():
    """La période se demande. Conseiller un renommage, c'est faire fabriquer la donnée."""
    from src.transformers.s4a_csv_parser import S4ACSVParser

    parser = S4ACSVParser()
    with pytest.raises(MissingFromFilenameError) as exc:
        parser._detect_window("export.csv")
    assert exc.value.field == "window"
    message = str(exc.value).lower()
    for forbidden in ("renomm", "rename"):
        assert forbidden not in message, (
            f"le message dit {forbidden!r} : il demande à l'artiste d'inventer la "
            "période dans le nom du fichier, sans aucun moyen de la vérifier."
        )

    assert parser._detect_window("export.csv", "28d") == "28d"
    assert parser._detect_window("export.csv", "12m") == "12m"


def test_the_admin_import_passes_the_filename():
    """`_upload_s4a` annonçait « ✅ 0 ligne(s) importée(s) » : il omettait le nom.

    Le titre du morceau n'existe que dans le nom du fichier. Cet appel ne le
    transmettait pas, donc `parse_timeline` rendait `[]` et l'écran affichait un
    succès vert pour un geste sans effet.
    """
    import ast
    import pathlib

    src = pathlib.Path("src/dashboard/views/admin.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_upload_s4a")
    calls = [n for n in ast.walk(fn)
             if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute)
             and n.func.attr == "parse_timeline"]
    assert calls, "_upload_s4a n'appelle plus parse_timeline — garde à repointer"
    for call in calls:
        assert any(kw.arg == "filename" for kw in call.keywords), (
            "parse_timeline sans `filename=` : le titre du morceau est introuvable, "
            "l'import rend 0 ligne et l'écran affiche quand même un succès."
        )
