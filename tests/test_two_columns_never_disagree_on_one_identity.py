"""Guard: « Saisi » et « Format » lisent la MÊME identité, pas deux copies.

Type: Utility
Uses: src.dashboard.utils.status_matrix, src.utils.tenant_identity
Triggers: pytest
Persists in: nothing

Error class `one-identity-two-readers`.

Spotify a deux domiciles : `artist_credentials.extra_config.spotify_artist_id` **et**
le miroir `saas_artists.spotify_artist_id`. `artist_readiness._identity` accepte l'un
OU l'autre pour dire « Saisi » ; `status_matrix.read_identities` ne lisait que le
premier. Deux colonnes de la même ligne répondaient donc à la même question avec deux
lectures : « Saisi ✅ » à côté de « Format ? — forme non vérifiable pour cette
plateforme ». Signalé le 2026-09-08 sur Santé onboarding.

L'état est atteignable et il a été atteint : `clear_platform_identities` — le `--reset`
du bac à sable — efface les lignes de credentials, et un ré-onboarding réécrit le
miroir avant la ligne.

**Troisième lecture à faire l'erreur.** `declared_identities` l'avait faite, corrigée le
2026-08-26, docstring à l'appui (« two readers, one question, two answers ») ; la
colonne « Format », écrite le 2026-09-04, l'a refaite sans la connaître. Le garde
n'épingle donc pas un appel : il compare les DEUX lecteurs sur les mêmes données, ce
qui rougit quel que soit celui des deux qui dérive.
"""
from __future__ import annotations

import pytest

from src.dashboard.utils.status_matrix import _shape_cell, read_identities
from src.utils.tenant_identity import IDENTITY_MIRRORS, declared_identities


class _DB:
    """Une base à deux tables — c'est tout l'objet du test.

    Un stub qui rend la même chose aux deux requêtes ne pourrait pas voir l'écart :
    c'est précisément « le credential dit non, le miroir dit oui ».
    """

    def __init__(self, credential_rows, mirror_row) -> None:
        self.credential_rows, self.mirror_row = credential_rows, mirror_row

    def fetch_query(self, sql, params=None):  # noqa: ANN001
        if "saas_artists" in sql:
            return [self.mirror_row]
        return self.credential_rows


def _mirror_row(spotify_id):
    """La ligne `saas_artists`, dans l'ordre des colonnes que le lecteur demande."""
    cols = sorted(set(IDENTITY_MIRRORS.values()))
    return tuple(spotify_id if c == IDENTITY_MIRRORS.get("spotify") else None
                 for c in cols)


def test_an_identity_that_lives_only_on_the_mirror_is_read() -> None:
    """Aucune ligne de credentials, un miroir renseigné — l'état d'après un reset."""
    db = _DB(credential_rows=[], mirror_row=_mirror_row("7sbfafbLjNZGZJZjZ3xoPB"))
    identities = read_identities(db, 18)
    assert identities.get("spotify") == "7sbfafbLjNZGZJZjZ3xoPB", (
        "l'identité mirroitée n'est pas lue : la colonne « Format » affichera « ? — "
        "forme non vérifiable » à côté d'un « Saisi ✅ » sur la MÊME ligne")


def test_the_format_cell_is_green_not_unknown_on_a_mirrored_identity() -> None:
    """Le symptôme tel que l'artiste le lit, pas seulement la valeur intermédiaire."""
    db = _DB(credential_rows=[], mirror_row=_mirror_row("7sbfafbLjNZGZJZjZ3xoPB"))
    identities = read_identities(db, 18)
    state, glyph, _tip = _shape_cell({"key": "spotify", "status": "ok"}, identities)
    assert (state, glyph) == ("green", "✅"), (
        f"« Format » rend {glyph!r} sur une identité pourtant saisie et bien formée")


def test_both_readers_agree_on_the_same_data() -> None:
    """L'invariant, et la seule forme qui rougit quel que soit le lecteur qui dérive.

    `declared_identities` (le lecteur de « Saisi », côté readiness) et
    `read_identities` (celui de « Format ») doivent désigner le même ensemble de
    plateformes déclarées, sur les mêmes données.
    """
    cases = [
        ([], _mirror_row("7sbfafbLjNZGZJZjZ3xoPB")),                       # miroir seul
        ([("spotify", {"spotify_artist_id": "abc"})], _mirror_row(None)),  # credential seul
        ([("spotify", {"spotify_artist_id": "abc"})],
         _mirror_row("7sbfafbLjNZGZJZjZ3xoPB")),                           # les deux
        ([], _mirror_row(None)),                                           # rien
    ]
    for credential_rows, mirror_row in cases:
        db = _DB(credential_rows, mirror_row)
        by_format = set(read_identities(db, 18))
        extra_by_platform = {p: e for p, e in credential_rows}
        cols = sorted(set(IDENTITY_MIRRORS.values()))
        mirrors = {logical: dict(zip(cols, mirror_row)).get(col)
                   for logical, col in IDENTITY_MIRRORS.items()}
        by_saisi = declared_identities(extra_by_platform, mirrors)
        assert by_format == by_saisi, (
            f"les deux lecteurs divergent sur {credential_rows!r}/{mirror_row!r} : "
            f"« Format » voit {sorted(by_format)}, « Saisi » voit {sorted(by_saisi)}")


def test_an_unreadable_mirror_never_breaks_the_column() -> None:
    """Le miroir est un complément : illisible, « Format » retombe sur le credential."""

    class _Boom(_DB):
        def fetch_query(self, sql, params=None):  # noqa: ANN001
            if "saas_artists" in sql:
                raise RuntimeError("connection lost")
            return self.credential_rows

    db = _Boom([("spotify", {"spotify_artist_id": "abc"})], _mirror_row(None))
    assert read_identities(db, 18).get("spotify") == "abc"


def test_spotify_is_actually_mirrored() -> None:
    """Sans miroir déclaré, tout ce fichier testerait le vide."""
    assert IDENTITY_MIRRORS.get("spotify"), (
        "aucun miroir pour Spotify — garde à repointer, il ne mesure plus rien")
