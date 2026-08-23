"""
Guard — aucun guide montré à un artiste ne lui demande une Redirect URI.

Type: Sub
Uses: pathlib, re
Triggers: pytest
Depends on: src/dashboard/content/credential_guides*.py
Persists in: nothing

Error class: dead-content-that-still-ships.

Mesuré le 2026-08-23 sur les notes d'un test artiste : « web api on peut pas cocher et
uri non bonne entre pdf et autre : localhost 8888 », « rajout de s sur uri ».

Deux corpus de guides coexistaient. Le corpus FRANÇAIS vivant dit, depuis le passage au
modèle central (ADR-006), « **tu n'as rien à créer** — colle le lien de ta page artiste ».
Le corpus ANGLAIS, lui, était resté sur le modèle d'avant : il demandait de créer une app,
de cocher **Web API** et de saisir `http://127.0.0.1:8888/callback`. Et il n'était pas mort
— il est **expédié dans le PDF d'onboarding** quand `lang == "en"`.

Le `8888` vient du défaut de `spotipy` (`SpotifyOAuth`), recopié à trois orthographes
différentes dans le dépôt (`127.0.0.1:8888`, `localhost:8888`, `http://localhost`), toutes
en `http://` — et la forme `localhost` est justement celle que le tableau de bord Spotify
**refuse désormais**.

Sous le modèle central, un artiste ne crée aucune app : lui parler de Redirect URI n'est
pas seulement inexact, c'est lui demander une étape qui n'existe pas.
"""

import re
from pathlib import Path

_CONTENT = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "content"
_ARTIST_GUIDES = ("credential_guides.py", "credential_guides_en.py")

# Le mot peut légitimement apparaître dans la note ADMIN (« aucune Redirect URI utilisée »).
# Ce qui est interdit, c'est de DEMANDER une valeur : une URI concrète, ou la case à cocher.
_BANNED = (
    re.compile(r"127\.0\.0\.1:\d+"),
    re.compile(r"localhost:\d+"),
    re.compile(r"http://localhost\b"),
    re.compile(r"[Tt]ick \*\*Web API\*\*"),
    re.compile(r"[Cc]ocher \*\*Web API\*\*"),
)


def test_the_guides_exist():
    for name in _ARTIST_GUIDES:
        assert (_CONTENT / name).is_file(), f"{name} a disparu"


def test_no_artist_guide_asks_for_a_redirect_uri():
    offenders = []
    for name in _ARTIST_GUIDES:
        text = (_CONTENT / name).read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            for pattern in _BANNED:
                if pattern.search(line):
                    offenders.append(f"{name}:{line_no} → {line.strip()[:70]}")
    assert not offenders, (
        "un guide artiste demande une Redirect URI ou la case Web API :\n  "
        + "\n  ".join(offenders)
        + "\nSous le modèle central (ADR-006) l'artiste ne crée aucune app. Ces étapes "
          "n'existent pas pour lui, et l'URI citée était de surcroît une forme que "
          "Spotify refuse."
    )


def test_the_two_languages_tell_the_same_story():
    """Le guide EN était un miroir périmé du FR — c'est ça qui a coûté la session."""
    fr = (_CONTENT / "credential_guides.py").read_text(encoding="utf-8")
    en = (_CONTENT / "credential_guides_en.py").read_text(encoding="utf-8")
    # Le FR dit « tu n'as rien à créer » ; l'EN doit dire la même chose.
    assert "rien à créer" in fr, "le guide FR a changé de modèle — revoir ce garde"
    assert "nothing for you to create" in en, (
        "le guide EN ne porte plus le modèle central alors que le FR si. C'est "
        "exactement la divergence qui a envoyé un artiste créer une app Spotify dont "
        "il n'avait pas besoin."
    )
