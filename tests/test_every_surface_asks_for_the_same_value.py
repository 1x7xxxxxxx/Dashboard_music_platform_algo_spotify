"""Toutes les surfaces qui disent « ce qu'il faut fournir » doivent dire la même chose.

Type: Test
Uses: _registry (le champ), platform_value (la mise en route), artist_readiness
    (la matrice d'état), credential_guides FR/EN, le catalogue i18n
Depends on: src/dashboard/views/credentials/_registry.py,
    src/dashboard/content/platform_value.py, src/utils/artist_readiness.py,
    src/dashboard/content/credential_guides*.py
Persists in: nothing

La classe, vue DEUX FOIS en deux jours
--------------------------------------
2026-09-04, SoundCloud : « c'est bizarre, tu demandes de saisir l'URL d'artiste et tu
me demandes mon user ID numérique ». Le champ acceptait le lien ; son libellé nommait
l'identifiant numérique que la BASE finit par stocker.

Le même jour, Spotify : le champ s'appelait « Spotify Artist ID **ou** URL profil » —
un choix qui n'en est pas un, puisqu'on ne colle jamais l'ID. Et la matrice d'état
répondait encore « Renseigne ton User ID SoundCloud numérique » longtemps après que le
champ eut changé de nom : elle vit dans `src/utils/`, personne ne la relit en
retouchant un guide, et rien ne la comparait au champ.

Quatre à cinq surfaces répondent à « qu'est-ce que je dois fournir ? » — le libellé du
champ, la note du guide (× 2 langues), le `need` de la mise en route, l'`id_hint` de la
matrice. Elles vivent dans quatre fichiers, dans trois paquets. Aucune n'est fausse
toute seule ; c'est leur DÉSACCORD qui est le défaut, et un désaccord n'a pas de
fichier où le lire.

Ce que ce fichier affirme
-------------------------
Que la NATURE de la valeur demandée est la même partout, et que la vérité de référence
est l'`example` du champ — le seul endroit qui décrit ce que le code accepte
réellement. Il ne fige aucune formulation : on peut réécrire chaque phrase, pas
réclamer un numéro là où l'exemple est une URL.
"""
from __future__ import annotations

import pytest

from src.dashboard.content.credential_guides import CREDENTIAL_GUIDES
from src.dashboard.content.credential_guides_en import CREDENTIAL_GUIDES_EN
from src.dashboard.content.platform_value import BY_KEY
from src.dashboard.utils.i18n_catalog.credentials import EN
from src.dashboard.views.credentials._registry import PLATFORMS
from src.utils.artist_readiness import _PLATFORMS as READINESS

# Ce qu'on ne peut pas réclamer quand le champ attend un lien. La liste est courte et
# ne contient QUE des mots qui désignent un numéro : élargir à « ID » attraperait
# « Channel ID », qui est un identifiant opaque légitime et n'est pas un lien.
_SAYS_A_NUMBER = ("numérique", "numeric", "un nombre", "a number")

def _identity_field(key: str) -> dict:
    """Le champ qui porte l'identité : le premier non secret qui a un exemple.

    Écrit d'abord « l'unique champ non secret », ce qui excluait Spotify — deux champs
    non secrets, dont un optionnel sans exemple — c'est-à-dire la plateforme dont le
    défaut a motivé ce fichier. La portée d'un garde est le défaut, une fois de plus.
    """
    for f in PLATFORMS[key]["fields"]:
        if not f["secret"] and f.get("example"):
            return f
    return {}


_LINK_PLATFORMS = sorted(
    k for k in PLATFORMS
    if str(_identity_field(k).get("example", "")).startswith("http")
)


def test_at_least_one_platform_asks_for_a_link():
    """Non-vacuité : sans plateforme à lien, tout ce fichier passerait pour rien."""
    assert _LINK_PLATFORMS, (
        "aucun champ n'a une URL pour exemple — soit le registre a changé de forme, "
        "soit ce garde ne prouve plus rien")


def _hints(key: str) -> dict[str, str]:
    """Chaque phrase visible qui répond à « qu'est-ce que je dois fournir ? »."""
    out: dict[str, str] = {}
    out["libellé du champ (_registry)"] = _identity_field(key)["label"]

    if key in BY_KEY:
        out["mise en route (PlatformValue.need)"] = BY_KEY[key].need

    row = next((p for p in READINESS if p["key"] == key), None)
    if row:
        out["matrice d'état (id_hint)"] = row["id_hint"]

    for lang, guides in (("fr", CREDENTIAL_GUIDES), ("en", CREDENTIAL_GUIDES_EN)):
        guide = next((g for g in guides if g.key == key), None)
        if guide and guide.fields:
            out[f"guide {lang} — libellé"] = guide.fields[0].label
            if guide.fields[0].note:
                out[f"guide {lang} — note"] = guide.fields[0].note

    # La traduction, que le rendu PRÉFÈRE à la source : une clé périmée EST ce que lit
    # l'artiste anglophone.
    for suffix in ("field_1", "note_1"):
        val = EN.get(f"credentials.guide.{key}.{suffix}")
        if val:
            out[f"catalogue EN — {suffix}"] = val
    return out


@pytest.mark.parametrize("key", _LINK_PLATFORMS)
def test_no_surface_asks_for_a_number_when_the_field_takes_a_link(key):
    """La nature de la valeur, la même partout.

    L'`example` du champ est la référence parce que c'est la seule chaîne que le code
    doit littéralement accepter : elle ne peut pas dériver sans que la saisie casse.
    Un libellé, lui, peut mentir pendant des semaines.
    """
    offenders = {
        where: text for where, text in _hints(key).items()
        if any(bad in str(text).lower() for bad in _SAYS_A_NUMBER)
    }
    assert not offenders, (
        f"Le champ « {key} » attend un LIEN (exemple : "
        f"{_identity_field(key)['example']}), "
        "et ces surfaces réclament un numéro :\n  "
        + "\n  ".join(f"{w} → {t!r}" for w, t in offenders.items())
        + "\n\nElles répondent toutes à « qu'est-ce que je dois fournir ? ». Un "
          "artiste n'en lit pas quatre : il en lit une, et se demande laquelle croire."
    )


@pytest.mark.parametrize("key", _LINK_PLATFORMS)
def test_the_field_label_offers_no_choice_between_two_forms(key):
    """« Spotify Artist ID **ou** URL profil » proposait une décision inexistante.

    On ne colle jamais l'identifiant : on colle l'URL, et le code en extrait l'ID.
    Nommer les deux transforme un geste en arbitrage, sur un formulaire à un champ.
    """
    label = _identity_field(key)["label"]
    assert " ou " not in f" {label.lower()} " and " or " not in f" {label.lower()} ", (
        f"le libellé « {label} » offre un choix entre deux formes alors qu'une seule "
        "est collable"
    )
