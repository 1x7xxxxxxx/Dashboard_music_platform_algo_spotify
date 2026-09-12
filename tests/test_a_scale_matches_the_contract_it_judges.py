"""Le rouge de fraîcheur ne s'allume pas sur un comportement normal.

Type: Test
Uses: pytest, ast
Depends on: src/dashboard/utils/kpi_helpers.py, src/dashboard/views/home.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Signalé le 2026-09-12 : « c'est en rouge alors qu'on a que 3 jours de retard ». La
tuile « 📂 À déposer toi-même » passait au ROUGE au bout de 72 h, parce qu'un seul
barème servait deux contrats très différents :

  * une **API** tourne chaque matin — passer une nuit est anormal, deux est une
    panne. 24 h / 72 h est juste ;
  * un **CSV** est déposé à la main, et Spotify for Artists publie par semaine.
    Trois jours sans dépôt est un mardi ordinaire.

Le défaut n'est pas cosmétique, et c'est ce qui en fait une classe : **un rouge qui
s'allume sur un comportement normal cesse d'être lu.** Il ne dira plus rien le jour
où la source casse vraiment — le voyant est consommé par le bruit. C'est la même
famille que `watchdog-becomes-the-noise`, du côté de l'échelle et non du détecteur.

Ce que ce fichier tient
-----------------------
Le barème est DÉRIVÉ du contrat déclaré (`SOURCES_CONFIG[…]["kind"]`), pas écrit à
côté ; les deux barèmes sont distincts ; et la vue transmet bien le `kind`, sans
quoi tout retomberait en silence sur le défaut le plus strict.

Journal de mutation — 2026-09-12 : avec `freshness_status` rendu insensible à son
`kind`, le cas « CSV à 3 jours » rougit en nommant la couleur obtenue ; avec
l'appel de `home.py` privé de son `kind`, le test de transmission rougit.
"""
from __future__ import annotations

import ast
import datetime as _d
import pathlib
from datetime import timezone as _tz

import pytest

from src.dashboard.utils.kpi_helpers import SOURCES_CONFIG, freshness_status

_ROOT = pathlib.Path(__file__).resolve().parent.parent


# (âge en jours, kind, emoji attendu). Ces cas viennent de la DEMANDE, pas d'une
# intuition : « passe le seuil rouge à 30j et orange à partir de 1 semaine ».
_CASES = [
    (3, "csv", "🟢"),     # le cas signalé : trois jours de retard n'est pas une panne
    (6, "csv", "🟢"),
    (8, "csv", "🟠"),     # au-delà d'une semaine, ça mérite un coup d'œil
    (29, "csv", "🟠"),
    (31, "csv", "🔴"),    # un mois sans dépôt : la donnée est vraiment vieille
    (2, "api", "🟠"),     # une API garde son barème strict : elle tourne chaque nuit
    (3, "api", "🔴"),
]


@pytest.mark.parametrize("days,kind,expected", _CASES)
def test_the_colour_matches_the_contract(days, kind, expected) -> None:
    got = freshness_status(_d.datetime.now(_tz.utc) - _d.timedelta(days=days), kind)[0]
    assert got == expected, (
        f"une source `{kind}` vieille de {days} j s'affiche {got}, attendu {expected}.\n"
        "Un rouge qui s'allume sur un comportement normal cesse d'être lu — et il ne "
        "dira plus rien le jour où la source casse vraiment.")


def test_the_two_scales_are_actually_different() -> None:
    """NON-VACUITÉ : sans écart, les cas ci-dessus passeraient par coïncidence.

    Un `kind` accepté puis ignoré rendrait le paramètre décoratif, et ce fichier
    vert sur le défaut qu'il existe pour attraper.
    """
    age = _d.datetime.now(_tz.utc) - _d.timedelta(days=3)
    assert freshness_status(age, "csv")[0] != freshness_status(age, "api")[0], (
        "les deux barèmes rendent la même couleur à 3 jours : `kind` est accepté "
        "mais jamais lu, donc le paramètre est décoratif")


def test_the_default_is_the_STRICTER_scale() -> None:
    """Une source dont on ignore la nature est surveillée comme la plus exigeante.

    L'inverse — retomber sur le barème indulgent — laisserait une API en panne
    verte pendant une semaine, ce qui est le défaut d'origine retourné.
    """
    age = _d.datetime.now(_tz.utc) - _d.timedelta(days=3)
    assert freshness_status(age)[0] == freshness_status(age, "api")[0], (
        "le barème par défaut est le plus indulgent : une source non classée peut "
        "rester verte une semaine en panne")


def test_every_source_declares_the_contract_the_scale_reads() -> None:
    """Le barème est dérivé de la DÉCLARATION, donc chaque source doit en porter une."""
    missing = [s.get("label") for s in SOURCES_CONFIG
               if s.get("kind") not in ("api", "csv")]
    assert not missing, (
        f"source(s) sans `kind` : {missing}. Leur fraîcheur retomberait sur le "
        "barème par défaut sans que personne l'ait décidé.")


def test_the_view_passes_the_contract_to_the_scale() -> None:
    """Le barème existe et n'est pas branché : la classe payée six fois ici.

    Lu dans l'ARBRE : une recherche de texte trouverait `kind` dans cette docstring
    et dans les commentaires voisins, et le cliquet du dépôt refuse les gardes
    textuels.
    """
    tree = ast.parse((_ROOT / "src/dashboard/views/home.py").read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "freshness_status"]
    assert calls, "`home.py` n'appelle plus `freshness_status`"
    with_kind = [n for n in calls if len(n.args) >= 2 or any(k.arg == "kind"
                                                             for k in n.keywords)]
    assert with_kind, (
        "aucun appel de `freshness_status` dans l'accueil ne transmet le contrat de "
        "la source : les deux barèmes existent et la grille retombe en silence sur "
        "celui des API, donc un CSV de trois jours est de nouveau rouge.")
