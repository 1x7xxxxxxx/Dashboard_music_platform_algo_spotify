"""Filet: les rapprochements qui MARCHENT aujourd'hui en production doivent survivre.

Type: Utility
Uses: src.utils.track_matching, src.utils.track_mapping_suggest
Triggers: pytest
Persists in: nothing

Error class `an-optimisation-that-degrades-what-worked`.

Le rapprochement des titres décide si les écoutes Spotify, les lectures Apple et les
plays SoundCloud s'additionnent SUR LE BON MORCEAU. Il se trompe en silence : aucune
exception, aucun compte qui change, juste des chiffres faux en aval. Et le seuil
d'auto-acceptation est à 0,80 — au-dessus, personne ne relit.

Mesuré le 2026-09-06 sur les titres RÉELS du locataire 18 en production :
**21 rapprochements corrects sur 21**, et les 6 intrus (edits DJ d'autres artistes,
mix maison) écartés sous 0,21.

Ce fichier n'est donc pas une liste de vœux : c'est un CLICHÉ de ce qui fonctionne.
Il existe parce que l'étape suivante consiste à modifier l'algorithme, et que le
risque d'une passe d'optimisation sur un algorithme à 21/21 est de le DÉGRADER.

Les titres sont recopiés tels quels de la base de production — accents, apostrophes,
`_` de nom de fichier, `?` d'Apple, préfixe d'artiste et suffixes `(free download)`
de SoundCloud compris. Ne pas les « nettoyer » : c'est exactement ce bruit-là que
l'algorithme doit absorber.
"""
from __future__ import annotations

import pytest

from src.utils.track_mapping_suggest import (
    artist_noise_tokens,
    rank_track_candidates,
    title_similarity,
)

# La vue passe le nom de l'artiste au moteur (`_artist_noise`), parce que SoundCloud
# et YouTube le préfixent au titre. Le filet le passe aussi : un filet qui n'appelle
# pas le moteur comme la production l'appelle ne garde pas la production.
_NOISE = artist_noise_tokens("1x7xxxxxxx")

# Les 10 morceaux canoniques du locataire 18 (`track_release_reference`).
_CANONICAL = [
    {"match_key": "ca te derange pas si je joue avec ton tapis",
     "title": "Ca te dérange pas si je joue avec ton tapis_", "release_date": None},
    {"match_key": "ca te derange pas si je joue avec ton tapis remix",
     "title": "Ca te dérange pas si je joue avec ton tapis_ - Remix", "release_date": None},
    {"match_key": "je ne parle pas tres bien le francais",
     "title": "Je ne parle pas très bien le français - Original", "release_date": None},
    {"match_key": "je ne parle pas tres bien le francais remix",
     "title": "Je ne parle pas très bien le français - Remix", "release_date": None},
    {"match_key": "kimono a semelle de fer",
     "title": "Kimono à semelle de fer", "release_date": None},
    {"match_key": "kimono a semelle de fer remix",
     "title": "Kimono à semelle de fer - Remix", "release_date": None},
    {"match_key": "o chiotte l arbitre tucome back",
     "title": "Ô Chiotte l'arbitre Tucome Back - Original", "release_date": None},
    {"match_key": "qui a bu le crachoir du saloon",
     "title": "Qui a bu le crachoir du saloon _", "release_date": None},
    {"match_key": "qui a sali mon slip avec de la gadoue",
     "title": "Qui a sali mon slip avec de la gadoue_", "release_date": None},
    {"match_key": "qui a sali mon slip avec de la gadoue remix",
     "title": "Qui a sali mon slip avec de la gadoue_ - Remix", "release_date": None},
]

# (titre tel qu'il est écrit sur la plateforme, match_key canonique attendu)
# Apple met la version entre parenthèses, garde les accents et le `?`.
_APPLE = [
    ("Ça te dérange pas si je joue avec ton tapis?",
     "ca te derange pas si je joue avec ton tapis"),
    ("Ça te dérange pas si je joue avec ton tapis? (Remix)",
     "ca te derange pas si je joue avec ton tapis remix"),
    ("Je ne parle pas très bien le français",
     "je ne parle pas tres bien le francais"),
    ("Je ne parle pas très bien le français (Remix)",
     "je ne parle pas tres bien le francais remix"),
    ("Kimono à semelle de fer", "kimono a semelle de fer"),
    ("Kimono à semelle de fer (Remix)", "kimono a semelle de fer remix"),
    ("Ô Chiotte l'arbitre Tucome Back", "o chiotte l arbitre tucome back"),
    ("Qui a bu le crachoir du saloon ?", "qui a bu le crachoir du saloon"),
    ("Qui a sali mon slip avec de la gadoue?",
     "qui a sali mon slip avec de la gadoue"),
    ("Qui a sali mon slip avec de la gadoue? (Remix)",
     "qui a sali mon slip avec de la gadoue remix"),
]

# SoundCloud préfixe du nom d'artiste et suffixe « free download » en casse variable.
_SOUNDCLOUD = [
    ("1x7xxxxxxx - Ca Te Dérange Pas Si Je Joue Avec Ton Tapis ?",
     "ca te derange pas si je joue avec ton tapis"),
    ("1x7xxxxxxx - Ca Te Dérange Pas Si Je Joue Avec Ton Tapis ? (REMIX)",
     "ca te derange pas si je joue avec ton tapis remix"),
    ("1x7xxxxxxx - Je Ne Parle Pas Très Bien Le Français",
     "je ne parle pas tres bien le francais"),
    ("1x7xxxxxxx - Je Ne Parle Pas Très Bien Le Français (REMIX)",
     "je ne parle pas tres bien le francais remix"),
    ("1x7xxxxxxx - KIMONO À SEMELLE DE FER (free download)",
     "kimono a semelle de fer"),
    ("1x7xxxxxxx - Kimono À Semelle De Fer (REMIX) Free Download",
     "kimono a semelle de fer remix"),
    ("1x7xxxxxxx - Qui a sali mon slip avec de la gadoue ? (free download)",
     "qui a sali mon slip avec de la gadoue"),
    ("1x7xxxxxxx - Qui A Sali Mon Slip Avec De La Gadoue (REMIX) Free download",
     "qui a sali mon slip avec de la gadoue remix"),
    ("Ô Chiotte L'arbitre Tucome back (Free DL)", "o chiotte l arbitre tucome back"),
    ("Qui a bu le crachoir du saloon ? (Free Download)", "qui a bu le crachoir du saloon"),
]

# Ce que l'artiste héberge sur SoundCloud sans qu'il figure DANS CETTE RÉFÉRENCE.
#
# Deux catégories, et la nuance compte. « Gorillaz - Clint Eastwood », « Souls Of
# Mischief », « The cardigans », « HOUSE MUSIC MIX #3 » sont des edits et des mix :
# ils ne seront jamais une sortie. « FEET FIRST » et « BÔ BUN MON BON MONSIEUR »,
# eux, SONT de vraies sorties de l'artiste — mesuré le 2026-09-06, elles portent un
# ISRC dans le relevé du distributeur — mais l'export S4A « 12 mois » ne les
# contient pas, car il ne montre que ce qui a été écouté sur douze mois.
#
# C'est pour ça que `rebuild_release_reference` lit désormais AUSSI le relevé du
# distributeur : 2 morceaux sur 12, soit 17 % du catalogue, étaient invisibles.
#
# Ici la référence reste volontairement celle des 10 titres S4A : ce fichier mesure
# le MOTEUR, pas la construction de la référence. Face à ces 10 titres, aucun de ces
# libellés ne doit franchir le seuil — c'est vrai des edits comme des sorties
# absentes, et pour la même raison : on ne rattache pas ce qu'on ne connaît pas.
_INTRUDERS = [
    "1x7xxxxxxx - FEET FIRST (free download)",
    "1x7xxxxxxx - Patte Velours 1ère Vitesse (free download)",
    "BÔ BUN MON BON MONSIEUR",
    "Gorillaz - Clint Eastwood (1x7xxxxxxx techno edit)",
    "HOUSE MUSIC MIX #3 BACK TO OLD SCHOOL",
    "Souls Of Mischief - 93 'til infinity (1x7xxxxxxx techno edit)",
    "The cardigans - My favourite game (1x7xxxxxxx techno edit)",
]

_AUTO_ACCEPT = 0.80      # le seuil au-dessus duquel personne ne relit
_INTRUDER_CEILING = 0.50 # 🔴 dans la légende de la vue


@pytest.mark.parametrize("platform_title,expected_key",
                         _APPLE, ids=[t for t, _ in _APPLE])
def test_an_apple_title_finds_its_track(platform_title, expected_key):
    """Apple : parenthèses, accents conservés, `?` là où S4A a `_`."""
    top = rank_track_candidates(platform_title, _CANONICAL, top_n=1,
                                   noise_tokens=_NOISE)
    assert top, f"aucun candidat pour {platform_title!r}"
    assert top[0].match_key == expected_key, (
        f"{platform_title!r} rapproché de {top[0].title!r} au lieu de "
        f"{expected_key!r} — un rapprochement qui MARCHAIT en production le "
        "2026-09-06 vient d'être perdu.")
    assert top[0].score >= _AUTO_ACCEPT, (
        f"{platform_title!r} tombe à {top[0].score} : sous {_AUTO_ACCEPT}, "
        "l'artiste doit valider à la main ce qui s'associait tout seul.")


@pytest.mark.parametrize("platform_title,expected_key",
                         _SOUNDCLOUD, ids=[t for t, _ in _SOUNDCLOUD])
def test_a_soundcloud_title_finds_its_track(platform_title, expected_key):
    """SoundCloud : préfixe d'artiste, « free download », casse anarchique."""
    top = rank_track_candidates(platform_title, _CANONICAL, top_n=1,
                                   noise_tokens=_NOISE)
    assert top, f"aucun candidat pour {platform_title!r}"
    assert top[0].match_key == expected_key, (
        f"{platform_title!r} rapproché de {top[0].title!r} au lieu de "
        f"{expected_key!r}.")
    assert top[0].score >= _AUTO_ACCEPT, (
        f"{platform_title!r} tombe à {top[0].score}, sous {_AUTO_ACCEPT}.")


@pytest.mark.parametrize("intruder", _INTRUDERS)
def test_an_intruder_never_reaches_the_threshold(intruder):
    """Un edit d'un autre artiste ne doit JAMAIS s'auto-associer à une sortie.

    C'est la moitié qui coûte le plus cher : un faux positif au-dessus de 0,80
    s'applique sans qu'un humain le voie, et gonfle les chiffres d'un morceau avec
    ceux d'un autre.
    """
    top = rank_track_candidates(intruder, _CANONICAL, top_n=1, noise_tokens=_NOISE)
    score = top[0].score if top else 0.0
    assert score < _INTRUDER_CEILING, (
        f"{intruder!r} obtient {score} contre {top[0].title!r} : au-dessus de "
        f"{_INTRUDER_CEILING} il n'est plus marqué 🔴, et au-dessus de "
        f"{_AUTO_ACCEPT} il s'associerait tout seul.")


def test_a_remix_never_outranks_its_own_original():
    """Base et remix sont deux sorties, avec deux dates. Les confondre fausse tout."""
    for base_title, base_key, remix_key in [
        ("Kimono à semelle de fer", "kimono a semelle de fer",
         "kimono a semelle de fer remix"),
        ("Qui a sali mon slip avec de la gadoue?",
         "qui a sali mon slip avec de la gadoue",
         "qui a sali mon slip avec de la gadoue remix"),
    ]:
        keys = [c.match_key for c in rank_track_candidates(base_title, _CANONICAL, top_n=3,
                                                   noise_tokens=_NOISE)]
        assert keys[0] == base_key, f"{base_title!r} → {keys}"
        assert remix_key not in keys, (
            f"le remix {remix_key!r} est proposé pour le titre de base "
            f"{base_title!r} : leurs statuts de version diffèrent, le score doit "
            "être nul et le candidat absent.")


def test_the_same_title_on_two_platforms_scores_one():
    """Le cas trivial doit rester trivial : deux écritures du même titre → 1,0."""
    assert title_similarity("Kimono à semelle de fer", "Kimono à semelle de fer") == 1.0
    assert title_similarity("Ça te dérange pas si je joue avec ton tapis?",
                            "Ca te dérange pas si je joue avec ton tapis_") == 1.0


class _FakeDB:
    """Base minimale : deux requêtes, une par source de la référence."""

    def __init__(self, s4a_rows, dist_rows):
        self._s4a, self._dist = s4a_rows, dist_rows
        self.upserted = None

    def fetch_query(self, sql, params=None):  # noqa: ANN001
        return self._dist if "imusician_sales_detail" in sql else self._s4a

    def upsert_many(self, table, data, conflict_columns, update_columns):  # noqa: ANN001
        self.upserted = data
        return len(data)


def test_the_reference_takes_what_the_s4a_export_misses():
    """L'export « 12 mois » ne montre que ce qui a été écouté sur douze mois.

    Mesuré le 2026-09-06 : 10 morceaux côté S4A, 12 côté relevé du distributeur.
    « Feet First » et « Bô bun mon bon monsieur » sont de vraies sorties, avec ISRC,
    et n'avaient AUCUNE entrée canonique — donc aucun titre de plateforme ne pouvait
    s'y rattacher, et ils passaient pour des intrus. 17 % du catalogue.
    """
    from src.utils.track_matching import rebuild_release_reference

    db = _FakeDB(
        s4a_rows=[("Kimono à semelle de fer", "2023-08-25")],
        dist_rows=[("Kimono à semelle de fer", None),       # déjà connu de S4A
                   ("Feet First", None),                    # absent de S4A
                   ("Bô bun mon bon monsieur", None),
                   ("Je ne parle pas très bien le français", "Remix")],
    )
    written = rebuild_release_reference(db, artist_id=18)
    keys = {row["match_key"]: row for row in db.upserted}

    assert "feet first" in keys, (
        "une sortie connue du seul distributeur reste absente de la référence")
    assert "bo bun mon bon monsieur" in keys
    assert keys["je ne parle pas tres bien le francais remix"], (
        "le champ Version de DDEX doit produire la clé « … remix », pas un doublon "
        "du titre de base")
    assert written == 4

    # S4A garde la main sur la DATE : le relevé ne connaît que des mois de vente.
    assert keys["kimono a semelle de fer"]["release_date"] == "2023-08-25"
    assert keys["kimono a semelle de fer"]["source"] == "s4a_songs_global"
    assert keys["feet first"]["source"] == "imusician_sales_detail"


def test_an_unreadable_distributor_statement_never_breaks_the_reference():
    """Une source d'appoint qui échoue ne doit pas emporter le socle."""
    from src.utils.track_matching import rebuild_release_reference

    class _Boom(_FakeDB):
        def fetch_query(self, sql, params=None):  # noqa: ANN001
            if "imusician_sales_detail" in sql:
                raise RuntimeError("table absente")
            return self._s4a

    db = _Boom(s4a_rows=[("Kimono à semelle de fer", "2023-08-25")], dist_rows=[])
    assert rebuild_release_reference(db, artist_id=18) == 1
