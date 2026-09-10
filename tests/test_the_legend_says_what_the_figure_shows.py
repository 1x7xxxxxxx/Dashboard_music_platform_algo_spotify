"""La légende de la figure se dérive de ce qu'elle montre, elle n'est pas écrite à côté.

Type: Test
Uses: pytest, ast
Depends on: src/dashboard/utils/platform_chart.py, src/dashboard/views/home.py
Persists in: nothing

Ce qui a été vu au rendu (2026-09-10)
-------------------------------------
Plainte de l'artiste : « pourquoi je n'ai pas YouTube sur le graphe, chacun à son
échelle, par année, 12 mois ? »

**L'absence de YouTube est délibérée et l'écran le disait déjà** : 24 jours mesurés sur
la fenêtre, répartis sur deux années civiles dont aucune n'atteint la moitié ; un total
annuel bâti là-dessus serait ~10× trop bas, et la note sous la figure le nomme. Ce
n'était pas le défaut.

Le défaut était à côté, et il y en avait trois — tous invisibles en lisant le code,
tous vus en rendant la page :

1. **La légende était FIXE** dans `views/home.py` : « Écoutes **du jour**, plateforme
   par plateforme. Un blanc dans la bande veut dire qu'on n'a pas de mesure ce
   jour-là. » Sous ce réglage, les trois affirmations étaient fausses en même temps —
   les points portaient des totaux ANNUELS, il n'y avait pas de bande mais des
   facettes, et un blanc ne parlait pas d'un jour.
2. **Le sous-titre annonçait « sur 2 années »** pour une fenêtre de 12 mois. Le nombre
   était juste — deux seaux annuels, la fenêtre étant à cheval sur deux années civiles
   — et le mot faux : cela se lit comme deux ans d'historique.
3. **`_UNSTACKED` était déclarée et lue nulle part**, et son contenu était faux :
   `share` empile, à 100 % même.

La cause commune est celle que l'audit de cette figure avait nommée (E) : *le texte est
écrit à côté du comportement, pas dérivé de lui*. La légende ne POUVAIT pas être juste
depuis la vue — celle-ci connaît le pas DEMANDÉ, et « Automatique » n'en est pas un.
Seul le module de la figure sait lequel a été retenu.

Le balayage de la classe a rendu **1 site sur 22** : les 21 autres textes qui disent
« quotidien » ou « chaque jour » parlent d'une chose réellement quotidienne (la collecte
nocturne, le scoring, la croissance Apple). Un correctif de masse les aurait tous
abîmés.
"""
from __future__ import annotations

import ast
import itertools
from functools import lru_cache
from pathlib import Path

import pytest

from src.dashboard.utils.platform_chart import (
    MODES, _STEP_BUCKETS, _STEP_UNITS, t_trend_caption)

ROOT = Path(__file__).resolve().parents[1]
_STEPS = ("day", "week", "year")


@lru_cache(maxsize=2)
def _tree(rel: str) -> ast.Module:
    """Lu à l'appel, pas à l'import — le test reste collectable sans sa cible."""
    return ast.parse((ROOT / rel).read_text(encoding="utf-8"))


@pytest.mark.parametrize("step,mode", list(itertools.product(_STEPS, MODES)))
def test_the_caption_names_the_step_it_is_drawn_at(step, mode) -> None:
    """Le produit cartésien : douze combinaisons, douze légendes distinctes à vérifier."""
    said = t_trend_caption(step, mode)
    wrong = {"day": ("de la semaine", "de l'année", "cette semaine-là", "cette année-là"),
             "week": ("du jour", "de l'année", "ce jour-là", "cette année-là"),
             "year": ("du jour", "de la semaine", "ce jour-là", "cette semaine-là")}[step]
    for bad in wrong:
        assert bad not in said, (
            f"au pas `{step}` en mode `{mode}`, la légende dit « {bad} » : "
            f"« {said} »")


@pytest.mark.parametrize("step", _STEPS)
def test_the_caption_never_speaks_of_a_band_in_facets(step) -> None:
    """Il n'y a pas de bande en petits multiples — chaque plateforme a sa facette."""
    said = t_trend_caption(step, "facets")
    assert "bande" not in said, (
        f"la légende parle d'une « bande » en mode facettes : « {said} ». Le lecteur "
        "cherche une pile qui n'est pas à l'écran.")


@pytest.mark.parametrize("step", _STEPS)
def test_a_running_total_is_not_described_as_a_quantity(step) -> None:
    """En cumulé, un point porte le total depuis le début, pas la quantité d'une période."""
    said = t_trend_caption(step, "cumulative")
    assert "depuis le début" in said, (
        f"en mode cumulé la légende décrit une quantité de période : « {said} ». Un "
        "point y porte le total accumulé — dire « écoutes de l'année » fait lire chaque "
        "point comme un an d'écoutes.")


def test_the_view_no_longer_carries_a_fixed_legend() -> None:
    """Si la vue la réécrit, elle repart avec le pas DEMANDÉ — donc fausse sur « auto »."""
    strings = {n.value for n in ast.walk(_tree("src/dashboard/views/home.py"))
               if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    for fragment in ("Écoutes **du jour**", "Un blanc dans la bande"):
        assert not any(fragment in s for s in strings), (
            f"`views/home.py` porte de nouveau la légende fixe ({fragment!r}). Elle ne "
            "peut pas être juste depuis là : la vue connaît le pas demandé, et "
            "« Automatique » n'en est pas un.")


def test_the_notes_renderer_receives_the_mode() -> None:
    """Sans le mode, la légende ne peut pas distinguer facettes et pile."""
    tree = _tree("src/dashboard/utils/platform_chart.py")
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "_render_notes"]
    assert calls, "plus aucun appel à `_render_notes` — les notes ne s'affichent plus"
    for call in calls:
        assert any(kw.arg == "mode" for kw in call.keywords), (
            "un appel à `_render_notes` ne transmet pas le mode : sa légende retombe "
            "sur le défaut « la bande », faux en facettes.")


def test_a_yearly_bucket_is_not_called_a_year() -> None:
    """Une fenêtre de 12 mois donne 2 seaux annuels, pas deux ans d'historique.

    Au pas jour et au pas semaine un seau vaut à peu près son unité, et la confusion
    n'existe pas — c'est pourquoi seul le pas annuel change de mot.
    """
    assert _STEP_BUCKETS["year"] != "années", (
        "le sous-titre compte des SEAUX et les nomme comme des unités de temps "
        "écoulé : « 8 490 écoutes sur 2 années » pour une fenêtre de 12 mois se lit "
        "comme deux ans de données.")
    for step in ("day", "week"):
        assert _STEP_BUCKETS[step] == _STEP_UNITS[step], (
            f"le pas `{step}` a changé de vocabulaire sans raison : un seau y vaut "
            "son unité, et deux mots pour la même chose est du bruit")

    # Et les trois sous-titres doivent LIRE `_STEP_BUCKETS`. Les avoir corrigés dans
    # le module sans les brancher serait la classe « du code correct que rien
    # n'atteint », déjà payée six fois ici.
    tree = _tree("src/dashboard/utils/platform_chart.py")
    reading = sum(1 for n in ast.walk(tree)
                  if isinstance(n, ast.Subscript)
                  and isinstance(n.value, ast.Name)
                  and n.value.id == "_STEP_BUCKETS")
    assert reading >= 3, (
        f"seulement {reading} sous-titre(s) lisent `_STEP_BUCKETS` — il y en a trois "
        "(pile, part, facettes), et celui qu'on oublie repart sur « années »")


def test_no_dead_constant_pretends_to_drive_the_subtitle() -> None:
    """`_UNSTACKED` était déclarée, jamais lue, ET fausse — `share` empile."""
    tree = _tree("src/dashboard/utils/platform_chart.py")
    names = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign)
             for t in n.targets if isinstance(t, ast.Name)}
    reads = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)
             and isinstance(n.ctx, ast.Load)}
    dead = {n for n in names
            if n.isupper() and n.startswith("_") and n not in reads}
    assert not dead, (
        f"constante(s) de module déclarée(s) et jamais lue(s) : {sorted(dead)}. "
        "`_UNSTACKED` a vécu ainsi jusqu'au 2026-09-10 en affirmant que `share` "
        "n'empile pas — c'est faux, elle empile à 100 %. Une constante morte est du "
        "bruit ; morte et fausse, elle enseigne quelque chose de faux.")
