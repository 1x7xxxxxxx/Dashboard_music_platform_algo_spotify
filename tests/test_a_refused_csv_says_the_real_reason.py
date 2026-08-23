"""
Guard — un CSV refusé nomme la cause, et pas un geste sans effet.

Type: Sub
Uses: importlib, io
Triggers: pytest
Depends on: src/dashboard/views/upload_csv.py
Persists in: nothing

Error class: detect-then-reject-with-the-wrong-advice.

Mesuré le 2026-08-23 en préparant le débogage du CSV de Benj.

L'export « Depuis le début » de Spotify for Artists (`…-songs-all.csv`) était **détecté**
par son propre nom de fichier, puis **rejeté** trois couches plus bas par `_detect_window`,
avec un message conseillant de **renommer le fichier**. Renommer ne corrige rien : Spotify
renvoie auditeurs et sauvegardes à ZÉRO sur cet export, c'est la donnée qui est
inutilisable. L'artiste était donc envoyé faire deux fois un geste sans effet.

Et le séparateur `;` — celui que produit **Excel en configuration française**, donc celui
qu'obtient tout artiste qui ouvre puis réenregistre son export — n'était pas testé : la
ligne d'en-tête se lisait comme une seule colonne géante, et le message disait « type non
reconnu » sans jamais nommer le séparateur.
"""

import importlib.util
import io
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_MOD = _ROOT / "src" / "dashboard" / "views" / "upload_csv.py"


def _module():
    spec = importlib.util.spec_from_file_location("upload_csv_under_test", _MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Upload(io.BytesIO):
    """Le minimum de l'objet que Streamlit passe : des octets et un `.name`."""

    def __init__(self, name: str, content: str, encoding: str = "utf-8"):
        super().__init__(content.encode(encoding))
        self.name = name


def test_a_semicolon_header_is_read_as_columns():
    """Excel FR produit des `;`. Sans ça, une colonne géante et « type non reconnu »."""
    mod = _module()
    f = _Upload("export.csv", "date;streams;listeners\n2026-01-01;10;5\n")
    cols = mod._read_headers(f)
    assert cols == ["date", "streams", "listeners"], (
        f"séparateur `;` non reconnu — colonnes lues : {cols}. C'est le format que "
        f"produit Excel en configuration française."
    )


def test_a_tab_header_still_works():
    """Le correctif ne doit pas casser DistroKid, qui est tabulé."""
    mod = _module()
    f = _Upload("distrokid.tsv", "Sale Month\tEarnings (USD)\n2026-01\t12.5\n")
    assert mod._read_headers(f) == ["Sale Month", "Earnings (USD)"]


def test_a_comma_header_still_works():
    mod = _module()
    f = _Upload("s4a.csv", "date,streams\n2026-01-01,10\n")
    assert mod._read_headers(f) == ["date", "streams"]


def test_the_since_start_export_is_refused_at_detection():
    """Et non trois couches plus bas, avec un conseil de renommage sans effet."""
    mod = _module()
    key = mod._detect_platform("mon-artiste-songs-all.csv",
                               ["song", "listeners", "streams", "saves"])
    assert key == "s4a_songs_all_rejected", (
        f"l'export « Depuis le début » est encore accepté à la détection (clé={key!r}) : "
        f"il sera rejeté plus bas par `_detect_window`, qui conseille de renommer le "
        f"fichier — un geste qui ne corrige rien, puisque la donnée elle-même est à zéro."
    )


def test_the_twelve_month_export_is_still_accepted():
    """Le remède proposé doit marcher, sinon le message ment."""
    mod = _module()
    key = mod._detect_platform("mon-artiste-songs-1year.csv",
                               ["song", "listeners", "streams", "saves", "release_date"])
    assert key == "s4a_songs_global", (
        f"clé={key!r} — le message de refus conseille l'export 12 mois ; s'il n'est pas "
        f"accepté, on envoie l'artiste dans un mur."
    )
