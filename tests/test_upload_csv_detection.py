"""Regression tests for CSV auto-detection + Spotify identity parsing.

Type: Utility
Guards the Benken onboarding incident (2026-06-19):
  - S4A / iMusician exports returned "type non reconnu" because detection required
    an exact filename token ('-timeline') + exact column names. Apple worked because
    it used flexible any()-of-aliases matching.
  - Spotify produced 0 rows for a new tenant because no per-tenant artist identity
    was captured.
"""
import pytest

from src.dashboard.views.upload_csv import _detect_platform
from src.dashboard.views.credentials._core import extract_spotify_artist_id


# ── CSV detection — the cases Benken's real exports hit ────────────────────────

@pytest.mark.parametrize("filename, columns, expected", [
    # S4A per-song timeline WITHOUT a '-timeline' filename token (the exact regression)
    ("spotify_export.csv", ["Date", "Streams"], "s4a"),
    ("Streams.csv", ["Date", "Écoutes"], "s4a"),
    # S4A audience detected by columns even without 'audience' in the filename
    ("export.csv", ["Date", "Listeners", "Streams"], "s4a_audience"),
    # S4A songs-all by columns (song + release_date/saves), no filename token
    ("catalogue.csv", ["Song", "Release_date", "Saves", "Streams"], "s4a_songs_global"),
    # iMusician summary detected via 'total revenue' (parser-aligned), not only 'track streams'
    ("rapport.csv", ["Statement date", "Release title", "Total revenue"], "imusician_summary"),
    ("rapport.csv", ["Release title", "Track streams"], "imusician_summary"),
    # iMusician sales (ISRC + shop) — unchanged, still specific
    ("ventes.csv", ["ISRC", "Shop", "Revenue"], "imusician_sales"),
    # Apple — unchanged (already worked for Benken)
    ("apple.csv", ["Morceau", "Écoutes"], "apple"),
    # DistroKid — unchanged specific signature
    ("dk.csv", ["Sale Month", "Earnings (USD)"], "distrokid_sales"),
])
def test_detect_platform_known(filename, columns, expected):
    assert _detect_platform(filename, columns) == expected


def test_detect_platform_unknown_returns_none():
    assert _detect_platform("mystery.csv", ["foo", "bar", "baz"]) is None


def test_detect_platform_is_case_insensitive():
    # Headers come in any case from real exports; detection lowercases + strips.
    assert _detect_platform("x.csv", ["  DATE ", "STREAMS"]) == "s4a"


# ── Spotify identity parsing — URL / URI / bare ID all normalise to the bare ID ─

_SPOTIFY_ID = "3TVXtAsR1Inumwj472S9r4"


@pytest.mark.parametrize("value", [
    _SPOTIFY_ID,
    f"https://open.spotify.com/artist/{_SPOTIFY_ID}",
    f"https://open.spotify.com/artist/{_SPOTIFY_ID}?si=abcdef",
    f"spotify:artist:{_SPOTIFY_ID}",
    f"  {_SPOTIFY_ID}  ",
])
def test_extract_spotify_artist_id(value):
    assert extract_spotify_artist_id(value) == _SPOTIFY_ID


def test_extract_spotify_artist_id_empty():
    assert extract_spotify_artist_id("") == ""
    assert extract_spotify_artist_id(None) == ""


# ── Les cas NÉGATIFS, absents jusqu'au 2026-09-18 ────────────────────────────
#
# Les cinq cas ci-dessus sont tous POSITIFS. C'est exactement pour ça que le défaut
# a survécu quinze semaines : `extract_spotify_artist_id` finissait par
# `return v if re.fullmatch(r'[0-9A-Za-z]{22}', v) else v` — les DEUX branches
# rendaient `v`, donc le contrôle de forme était décoratif — et aucun test ne
# demandait jamais ce qu'il advenait d'une entrée ILLISIBLE. Un jeu de tests qui
# n'exerce que le chemin heureux ne peut pas voir un repli faux.
#
# La valeur rendue atteint un SEGMENT DE CHEMIN d'URL sortante
# (`_platform_spotify.py`, `f'https://api.spotify.com/v1/artists/{artist_id}'`), et
# `requests` applique la suppression des segments `..` AVANT d'émettre : mesuré le
# 2026-09-18, `'../../v1/me'` produisait bien un appel à `https://api.spotify.com/v1/me`.

@pytest.mark.parametrize("value", [
    "me/accounts",          # la charge utile du P1 Instagram du 2026-08-22
    "../../v1/me",          # traversée de chemin, effective contre api.spotify.com
    "../../../me",
    "x?fields=id",          # `?` n'est pas encodé : le locataire choisit la requête
    "@evil.example/x",
    "pas-un-id",
    "3TVXtAsR1Inumwj472S9r",        # 21 caractères — un de moins
    "3TVXtAsR1Inumwj472S9r44",      # 23 — un de trop
    "3TVXtAsR1Inumwj472S9r-4",      # bon compte, caractère hors base-62
])
def test_an_unreadable_spotify_reference_yields_nothing(value):
    """Le repli rend `''`, comme la docstring le promet — jamais l'entrée brute.

    Rendre `value` ici laisserait une valeur choisie par le locataire atteindre une
    URL sortante. Rendre `''` la fait refuser en amont, avec un message qui nomme la
    forme attendue.
    """
    assert extract_spotify_artist_id(value) == "", (
        f"`{value!r}` ressort intact : le repli rend l'entrée brute au lieu de `''`, "
        "et cette valeur atteint un segment de chemin d'URL sortante."
    )


def test_the_shape_comes_from_the_one_registry():
    """La forme est celle de `PLATFORM_IDENTITIES`, pas une seconde regex locale.

    Avant le 2026-08-22, ce registre existait en CINQ exemplaires qui divergeaient.
    Une copie locale dans l'extracteur rouvrirait exactement cette porte : le jour où
    Spotify changerait de longueur d'identifiant, deux endroits devraient bouger et un
    seul bougerait.
    """
    from src.utils.tenant_identity import PLATFORM_IDENTITIES, identity_is_well_formed

    motif = PLATFORM_IDENTITIES["spotify"].pattern
    assert motif == r"[0-9A-Za-z]{22}", (
        "le motif du registre a changé — ce test doit être relu, pas ajusté")
    # Le contrat croisé : ce que l'extracteur accepte est exactement ce que le
    # registre déclare bien formé.
    for v in (_SPOTIFY_ID, "me/accounts", "pas-un-id", ""):
        rendu = extract_spotify_artist_id(v)
        assert bool(rendu) == identity_is_well_formed("spotify", v) or rendu == _SPOTIFY_ID, (
            f"désaccord sur {v!r} : extracteur → {rendu!r}, registre → "
            f"{identity_is_well_formed('spotify', v)}")
