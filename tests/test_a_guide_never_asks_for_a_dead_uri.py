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
    """Le guide EN était un miroir périmé du FR — c'est ça qui a coûté la session.

    Ancré sur la STRUCTURE, plus sur une phrase. La version d'avant cherchait
    littéralement « rien à créer » côté FR et « nothing for you to create » côté EN.
    Elle a échoué le 2026-08-30 quand ces deux intros ont été raccourcies — sur une
    reformulation, pas sur une divergence. Son propre message le disait : « le guide
    FR a changé de modèle — revoir ce garde ».

    Ce qu'il faut vraiment tenir : les deux langues décrivent le même parcours. Un
    nombre d'étapes différent EST la divergence qui a envoyé un artiste créer une app
    Spotify dont il n'avait pas besoin — l'EN portait encore l'ancien modèle avec ses
    étapes en plus.
    """
    import sys
    sys.path.insert(0, str(_CONTENT.parents[3]))
    import src.dashboard.content.credential_guides as fr_mod
    import src.dashboard.content.credential_guides_en as en_mod

    def by_key(mod):
        return {v.key: v for v in vars(mod).values()
                if hasattr(v, "key") and hasattr(v, "steps")}

    fr, en = by_key(fr_mod), by_key(en_mod)
    assert set(fr) == set(en), (
        f"plateformes présentes dans une langue seulement : {set(fr) ^ set(en)}")

    drift = [f"{k}: FR {len(fr[k].steps)} étapes / EN {len(en[k].steps)}"
             for k in sorted(fr) if len(fr[k].steps) != len(en[k].steps)]
    assert not drift, (
        "les deux langues ne décrivent plus le même parcours :\n  " + "\n  ".join(drift)
        + "\nUne étape présente dans une seule langue, c'est un artiste anglophone à "
          "qui on demande un geste que le modèle central a supprimé — ou l'inverse.")

    fdrift = [f"{k}: FR {len(fr[k].fields)} champs / EN {len(en[k].fields)}"
              for k in sorted(fr) if len(fr[k].fields) != len(en[k].fields)]
    assert not fdrift, "champs à saisir divergents :\n  " + "\n  ".join(fdrift)


def test_a_prefilled_portal_link_is_a_template_that_can_resolve():
    """`portal_search_url` must carry {q}, and must not be a path that 404s empty.

    Measured 2026-08-30, because the shape was proposed and then withdrawn during the
    test session itself:

        https://open.spotify.com/search/NASA/artists  → 200
        https://open.spotify.com/artist/              → 500
        https://open.spotify.com                      → 200

    A search path takes the query as a PATH SEGMENT, so the artist name must be
    percent-encoded with `safe=""` — an unescaped `/` in a name like "AC/DC" would
    otherwise split the path and silently search for something else.
    """
    from src.dashboard.content.credential_guides import CREDENTIAL_GUIDES

    for guide in CREDENTIAL_GUIDES:
        tpl = getattr(guide, "portal_search_url", None)
        if not tpl:
            continue
        assert "{q}" in tpl, (
            f"{guide.key}: portal_search_url has no {{q}} placeholder, so every artist "
            f"is sent to the same page: {tpl!r}"
        )
        stripped = tpl.replace("{q}", "")
        assert not stripped.rstrip("/").endswith("/artist"), (
            f"{guide.key}: {tpl!r} degenerates to a bare /artist/ path, which answers "
            "500. That exact URL was proposed and withdrawn during the 2026-08-30 test."
        )
