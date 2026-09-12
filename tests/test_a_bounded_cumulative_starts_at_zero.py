"""Sur une fenêtre bornée, toutes les courbes partent de zéro — sinon l'une écrase tout.

Type: Test
Uses: pytest, platform_chart.render_platform_chart
Depends on: src/dashboard/utils/platform_chart.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Signalé le 2026-09-13 : « Bug sur la vue cumulé 30 jours je n'ai pas spotify alors que
c'est ma première source de revenue ».

Spotify ÉTAIT tracée. Elle était **invisible**, et la cause est une pile qui mélangeait
deux références. Mesuré en production, fenêtre de 30 jours, artiste 1 :

    Spotify    →     545   (somme courante DANS la fenêtre)
    YouTube    → 118 300   (niveau ABSOLU, cumul à vie)
    SoundCloud →  23 500   (idem)

Spotify pesait **0,4 % de la pile** — moins d'un pixel — alors que c'est la seule
plateforme qui ait réellement bougé ces trente jours. Les compteurs n'avaient pas « plus
d'écoutes » : ils portaient tout leur passé, que la fenêtre ne demandait pas. Empiler un
écart et un total revient à additionner deux choses différentes.

La propriété qui rend la figure lisible ET vérifiable est la même : **sur une fenêtre
bornée, le dernier point de chaque courbe vaut ce que sa boîte annonce pour cette
période.** Un lecteur peut poser le doigt sur la courbe et retrouver le chiffre.

⚠️ **Sauf sur « Depuis le début »**, où la question est « où j'en suis » et la réponse le
compteur à vie — 118 336, ce qu'affiche la boîte. Y retrancher le premier relevé ferait
dire 304 à la courbe et 118 336 à la tuile : le même défaut, dans l'autre sens.

Mutations vues rouges avant écriture (2026-09-13) :
  * `bounded=since is not None` remplacé par `bounded=False` →
    test_each_curve_ends_where_its_own_total_says ÉCHOUE en nommant les deux nombres ;
  * `bounded=True` inconditionnel →
    test_the_unbounded_view_keeps_the_lifetime_level ÉCHOUE.
"""
from __future__ import annotations

import datetime as _d
from unittest.mock import patch

import pytest

from src.dashboard.utils import platform_chart as pc

_DAYS = [_d.date(2025, 1, 1) + _d.timedelta(days=i) for i in range(400)]

# SPOTIFY : une source vraiment QUOTIDIENNE, qui repart de zéro sur toute fenêtre.
# YOUTUBE : un COMPTEUR déjà très haut avant la fenêtre — c'est lui qui écrasait tout.
_SERIES = {"spotify": [(d, 20) for d in _DAYS],
           "youtube": [(d, 1) for d in _DAYS]}
_LEVELS = {"youtube": [(d, 100_000 + i) for i, d in enumerate(_DAYS)]}


def _curves(since, until):
    """{nom: dernier point tracé} en mode cumulé."""
    figs: dict = {}
    with patch("streamlit.plotly_chart", lambda f, **k: figs.setdefault("f", f)), \
         patch("streamlit.caption", lambda *a, **k: None), \
         patch("streamlit.info", lambda *a, **k: None), \
         patch("streamlit.markdown", lambda *a, **k: None):
        drawn = pc.render_platform_chart(
            _SERIES, since=since, until=until, step="day", mode="cumulative",
            cumulative=_LEVELS, key=f"bnd_{since}_{until}")
    assert drawn, "la figure ne s'est pas rendue"
    out: dict = {}
    for t in figs["f"].data:
        if not t.name or "Aucune" in t.name:
            continue
        ys = [y for y in (t.y or []) if y is not None]
        if ys:
            out[t.name] = max(out.get(t.name, 0), ys[-1])
    return out


def test_each_curve_ends_where_its_own_total_says():
    """Fenêtre de 30 jours : chaque courbe finit sur le gain de CETTE période."""
    since, until = _DAYS[-31], _DAYS[-1]
    got = _curves(since, until)
    # Spotify : 31 journées à 20 écoutes.
    assert got.get("🎵 Spotify") == 620, (
        f"Spotify finit à {got.get('🎵 Spotify')} au lieu de 620 sur 31 jours à 20")
    # YouTube : le compteur gagne 1 par jour, donc 30 sur la fenêtre — et surtout
    # PAS ses 100 000 de passé, que la fenêtre ne demande pas.
    yt = got.get("🎬 YouTube")
    assert yt is not None and yt < 100, (
        f"YouTube finit à {yt} sur une fenêtre de 30 jours : la courbe porte son "
        "cumul à VIE alors que Spotify porte une somme courante de la fenêtre. "
        "Empiler les deux revient à additionner un écart et un total — mesuré en "
        "production le 2026-09-13, Spotify tombait à 0,4 % de la pile et devenait "
        "invisible alors que c'est la seule plateforme qui avait bougé.")


def test_the_dominant_platform_of_the_window_is_actually_dominant():
    """Le test précédent passerait encore si les deux courbes étaient minuscules."""
    got = _curves(_DAYS[-31], _DAYS[-1])
    total = sum(got.values())
    assert total and got["🎵 Spotify"] / total > 0.8, (
        f"Spotify ne pèse que {got['🎵 Spotify'] / total:.1%} de la pile alors "
        "qu'elle porte 620 des 650 écoutes de la fenêtre. C'est la plainte d'origine : "
        "« je n'ai pas spotify alors que c'est ma première source de revenue ».")


def test_the_unbounded_view_keeps_the_lifetime_level():
    """« Depuis le début » répond « où j'en suis » — le compteur à vie."""
    got = _curves(None, None)
    yt = got.get("🎬 YouTube")
    assert yt is not None and yt > 100_000, (
        f"YouTube finit à {yt} sur « Depuis le début » : la courbe a été ramenée à "
        "zéro alors que la boîte annonce le compteur à VIE. La courbe dirait 399 et "
        "la tuile 100 399 — le défaut du 2026-09-13 dans l'autre sens.")


@pytest.mark.parametrize("days", [7, 30, 90])
def test_no_window_length_changes_the_rule(days):
    """La règle ne dépend pas de la longueur, seulement du fait d'être bornée."""
    got = _curves(_DAYS[-(days + 1)], _DAYS[-1])
    yt = got.get("🎬 YouTube")
    assert yt is not None and yt <= days + 1, (
        f"sur {days} jours, YouTube finit à {yt} — plus que ce que le compteur peut "
        f"avoir gagné ({days + 1} au maximum). Le niveau d'entrée n'a pas été "
        "retranché.")
