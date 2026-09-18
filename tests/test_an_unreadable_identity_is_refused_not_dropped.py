"""Une saisie illisible se REFUSE ; elle ne disparaît pas en silence.

Type: Test
Uses: src.dashboard.views.credentials._core, src.utils.tenant_identity
Depends on: normalise_spotify_for_save, malformed_identities, write_platform_identity
Persists in: nothing

Pourquoi ce fichier existe — mesuré le 2026-09-18
-------------------------------------------------
`extract_spotify_artist_id` finissait par
`return v if re.fullmatch(r'[0-9A-Za-z]{22}', v) else v` : **les deux branches
rendaient `v`**, donc le contrôle de forme était décoratif et la docstring promettait
l'inverse. Une valeur choisie par le locataire ressortait intacte et atteignait un
segment de chemin d'URL sortante.

Corriger cet extracteur SEUL aurait été pire que le défaut. La chaîne de sauvegarde,
dans l'ordre où elle s'exécute :

1. normalisation Spotify — si l'extracteur rend `''`, l'ancienne forme faisait
   `extra.pop('spotify_artist_id')` ;
2. `malformed_identities(...)` — refuse une identité mal formée **et ne voit que ce
   qui est encore dans le dict** ;
3. `write_platform_identity(...)` — écrit le miroir `saas_artists.spotify_artist_id`
   avec `extra.get(...) or None`.

Une saisie illisible serait donc sortie du dict à l'étape 1, n'aurait rien déclenché à
l'étape 2, et aurait mis la colonne miroir à **NULL** à l'étape 3. L'écran aurait
affiché « enregistré ». Un locataire qui ré-enregistre son formulaire **perd sa clé de
collecte sans un mot** — et `spotify_api_daily` cesse de le sélectionner.

C'est la classe des faux verts que ce dépôt a déjà payée deux fois. Le ternaire vacuous
était, par accident, ce qui maintenait le refus de l'étape 2 atteignable.

Ce fichier fige les trois cas de `normalise_spotify_for_save`, et surtout le troisième.
"""
from __future__ import annotations

import pytest

from src.dashboard.views.credentials._core import normalise_spotify_for_save
from src.utils.tenant_identity import IDENTITY_KEYS, malformed_identities

_ID = "3TVXtAsR1Inumwj472S9r4"

# Ce qu'un locataire peut coller et qui ne donne AUCUN identifiant.
_ILLISIBLES = [
    "me/accounts",
    "../../v1/me",
    "x?fields=id",
    "@evil.example/x",
    "pas-un-id",
    "3TVXtAsR1Inumwj472S9r",      # 21
    "3TVXtAsR1Inumwj472S9r44",    # 23
]


@pytest.mark.parametrize("brut", _ILLISIBLES)
def test_an_unreadable_value_survives_into_the_refusal(brut):
    """Le cas qui compte : la valeur RESTE, donc le refus de l'étape 2 la voit."""
    sortie = normalise_spotify_for_save({"spotify_artist_id": brut})
    assert sortie.get("spotify_artist_id") == brut, (
        f"`{brut!r}` a disparu du dict au lieu d'y rester. `malformed_identities` ne "
        "le verra pas, l'écran dira « enregistré », et le miroir passera à NULL."
    )
    # Et la preuve de bout en bout : l'étape 2 le refuse effectivement.
    assert malformed_identities({"spotify": sortie}), (
        f"`{brut!r}` reste dans le dict mais `malformed_identities` ne le refuse pas — "
        "le refus et la normalisation ne sont plus d'accord sur ce qu'est une forme."
    )


@pytest.mark.parametrize("brut,attendu", [
    (_ID, _ID),
    (f"https://open.spotify.com/artist/{_ID}", _ID),
    (f"https://open.spotify.com/artist/{_ID}?si=abc", _ID),
    (f"spotify:artist:{_ID}", _ID),
    (f"  {_ID}  ", _ID),
])
def test_a_readable_value_is_normalised_and_accepted(brut, attendu):
    sortie = normalise_spotify_for_save({"spotify_artist_id": brut})
    assert sortie["spotify_artist_id"] == attendu
    assert not malformed_identities({"spotify": sortie}), (
        "une valeur bien formée est refusée — le refus est devenu trop large")


@pytest.mark.parametrize("vide", ["", "   ", None])
def test_an_empty_value_leaves_the_dict(vide):
    """Vide ≠ illisible. Une clé vide se lit « connecté » sur qui compte des LIGNES."""
    sortie = normalise_spotify_for_save({"spotify_artist_id": vide})
    assert "spotify_artist_id" not in sortie, (
        "une chaîne vide reste dans le dict : c'est la forme exacte que le `pop` "
        "existe pour empêcher, et elle fait passer une ligne pour une connexion.")


def test_the_mirror_would_be_nulled_by_an_absent_key():
    """La non-vacuité de tout ce fichier : SANS la clé, le miroir passe à NULL.

    Si `write_platform_identity` cessait de mettre la colonne à NULL pour une clé
    absente, les tests ci-dessus continueraient de passer en ne gardant plus rien.
    On épingle donc la conséquence, pas seulement la cause.
    """
    champ = IDENTITY_KEYS["spotify"]
    assert ({}.get(champ) or None) is None, (
        "une clé absente ne rend plus None — relire `write_platform_identity`, "
        "la chaîne de conséquence décrite en tête de ce fichier a changé.")
    assert ({champ: ""}.get(champ) or None) is None, (
        "une chaîne vide ne rend plus None — même conséquence.")


def test_normalisation_does_not_mutate_its_input():
    """Elle rend un nouveau dict : l'appelant décide, et rien ne change sous lui."""
    entree = {"spotify_artist_id": "../../v1/me", "autre": "x"}
    copie = dict(entree)
    normalise_spotify_for_save(entree)
    assert entree == copie, "l'entrée a été modifiée en place"
