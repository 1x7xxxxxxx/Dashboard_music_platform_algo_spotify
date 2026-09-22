"""Le plan affiché sort du RÉSOLVEUR, jamais de la colonne brute.

Type: Test
Uses: ast, pytest
Depends on: src/dashboard/views/account.py, src/dashboard/auth.py
Persists in: nothing

Le défaut, mesuré le 2026-09-21
--------------------------------
La page « Mon compte » affichait `saas_artists.tier`, lue directement par sa
requête. Or `tier` n'est qu'un REPLI dans `get_artist_plan()`, qui lit d'abord
`artist_subscriptions` puis applique la précédence promo / essai de bienvenue /
`view_as`.

Mesuré en base le même jour : l'artiste 1 porte `tier = 'premium'` et **aucune
ligne dans `artist_subscriptions`**. Trois surfaces pouvaient donc afficher deux
vérités — le compte disait « premium » depuis une colonne que personne ne
maintient, pendant que la barre latérale et la facturation passaient par le
résolveur.

Classe : `a-display-that-reads-the-fallback-instead-of-the-resolver`. Elle ne
lève jamais : les deux valeurs sont des chaînes valides, et elles coïncident tant
que personne n'a de promo.

Ce que ce garde tient, et ce qu'il ne tient PAS
------------------------------------------------
Il tient : la page du compte ne SÉLECTIONNE plus `tier`, et elle appelle bien le
résolveur. Il ne tient PAS « personne ne lit jamais `tier` » — ce serait faux et
nuisible : `get_artist_plan()` DOIT le lire, c'est son repli, et `auth.py` est
donc exempté nommément.
"""
from __future__ import annotations

import ast
import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_VUE = _ROOT / "src" / "dashboard" / "views" / "account.py"

# LE seul lieu qui a le droit de lire la colonne : le résolveur lui-même.
_RESOLVEUR = "src/dashboard/auth.py"


def _chaines(path: pathlib.Path) -> list[str]:
    """Littéraux du module, docstrings exclues — ce fichier CITE `tier` en prose."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = set()
    for n in ast.walk(tree):
        corps = getattr(n, "body", None)
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                          ast.AsyncFunctionDef)) and corps \
                and isinstance(corps[0], ast.Expr) \
                and isinstance(corps[0].value, ast.Constant) \
                and isinstance(corps[0].value.value, str):
            docs.add(id(corps[0].value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docs]


def test_the_account_page_does_not_select_the_raw_tier() -> None:
    fautifs = [" ".join(s.split())[:100] for s in _chaines(_VUE)
               if re.search(r"\bSELECT\b", s, re.I)
               and re.search(r"\b(?:a|sa)\.tier\b|\btier\s+AS\b", s, re.I)]
    assert not fautifs, (
        "`account.py` sélectionne la colonne `tier` :\n  " + "\n  ".join(fautifs)
        + "\nC'est le REPLI de `get_artist_plan()`, pas la réponse. L'artiste 1 "
          "porte `tier='premium'` sans aucune ligne d'abonnement : la page "
          "pouvait annoncer un plan que la facturation contredit.")


def test_the_account_page_calls_the_resolver() -> None:
    """NON-VACUITÉ : « ne lit pas la colonne » est vrai aussi d'une page muette."""
    src = _VUE.read_text(encoding="utf-8")
    tree = ast.parse(src)
    appelle = any(
        isinstance(n, ast.Call)
        and (getattr(n.func, "id", None) == "get_artist_plan"
             or getattr(n.func, "attr", None) == "get_artist_plan")
        for n in ast.walk(tree))
    assert appelle, (
        "`account.py` n'appelle pas `get_artist_plan()` : soit la page n'affiche "
        "plus de plan, soit elle est revenue à une lecture directe. Le test "
        "précédent ne prouve alors plus rien.")


def test_the_resolver_keeps_its_fallback() -> None:
    """LA PRÉMISSE, et elle protège l'exemption.

    Ce garde n'interdit `tier` qu'à l'affichage PARCE QUE le résolveur s'en
    charge. Si `auth.py` cessait de lire la colonne, l'interdiction deviendrait
    un contresens : plus personne ne saurait le plan d'un artiste sans ligne
    d'abonnement — c'est-à-dire de l'artiste 1 aujourd'hui.
    """
    src = (_ROOT / _RESOLVEUR).read_text(encoding="utf-8")
    assert re.search(r"\btier\b", src), (
        f"{_RESOLVEUR} ne mentionne plus `tier` : le repli a disparu. Soit la "
        "colonne est morte et il faut la retirer partout, soit c'est une "
        "régression — dans les deux cas, ce garde ne doit plus interdire sa "
        "lecture ailleurs sans qu'on y regarde.")


def test_the_detector_sees_the_query_it_was_written_for() -> None:
    """La requête EXACTE qui vivait dans la page, et la version saine."""
    fautive = ("SELECT u.id, u.username, a.name AS artist_name, "
               "a.slug AS artist_slug, a.tier AS artist_tier FROM saas_users u")
    assert re.search(r"\b(?:a|sa)\.tier\b|\btier\s+AS\b", fautive, re.I)
    saine = ("SELECT u.id, u.username, a.name AS artist_name FROM saas_users u "
             "LEFT JOIN saas_artists a ON u.artist_id = a.id")
    assert not re.search(r"\b(?:a|sa)\.tier\b|\btier\s+AS\b", saine, re.I)
