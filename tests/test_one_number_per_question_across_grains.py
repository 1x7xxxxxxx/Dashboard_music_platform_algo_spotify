"""La figure « par période » donne le MÊME total à tous les pas, et nomme son écart.

Type: Test
Uses: pytest, platform_chart.render_platform_chart, home._render_tiles
Depends on: src/dashboard/utils/platform_chart.py, src/dashboard/views/home.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Signalé le 2026-09-13 : « j'ai des chiffres qui disent n'importe quoi pour le non
cumulé ». Mesuré en production, artiste 1, historique complet :

    pas JOUR  → la figure totalise **138** vues YouTube
    pas MOIS  → la figure totalise **304** vues YouTube

Même plateforme, même période, deux réponses. Et depuis que le grain se dérive de la
fenêtre, l'artiste voit le chiffre changer en déplaçant un filtre de période, **sans
avoir rien choisi**. C'est la définition d'un chiffre qui dit n'importe quoi.

La cause était une exception : au pas du jour, les compteurs retombaient sur la somme
des ÉCARTS QUOTIDIENS. Un écart n'existe qu'entre deux jours CONSÉCUTIFS, et YouTube
n'est relevée que 39 % des jours — 55 % du gain était jeté. La croissance d'un
compteur se lit sur ses NIVEAUX, et c'est vrai à tous les pas.

Le second écart n'est pas un défaut mais il se nomme : la boîte annonce **118 336**
(compteur à VIE) quand la figure en dessine **304** (ce que nous avons vu croître
depuis le 29/11/2025). Les 118 032 vues antérieures ont eu lieu, mais aucune date ne
peut les porter — une figure « en fonction du temps » ne peut pas les dessiner, et les
répartir uniformément inventerait une histoire.

Mutations vues rouges avant écriture (2026-09-13) :
  * `served` remis à `[]` au pas du jour en mode absolu →
    test_every_grain_totals_the_same ÉCHOUE en nommant les deux totaux ;
  * la mention du compteur à vie retirée de l'infobulle →
    test_a_lifetime_counter_says_what_the_curve_cannot_draw ÉCHOUE.
"""
from __future__ import annotations

import ast
import datetime as _d
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import pytest

from src.dashboard.utils import platform_chart as pc
from src.dashboard.views.home import _render_tiles

_CHART = Path(__file__).resolve().parents[1] / "src/dashboard/utils/platform_chart.py"

_DAYS = [_d.date(2025, 1, 1) + _d.timedelta(days=i) for i in range(400)]
# UN COMPTEUR RELEVÉ CINQ JOURS SUR SEPT : assez dense pour que les seaux passent le
# PLANCHER DE COUVERTURE (50 % des jours), assez troué pour que la somme des écarts
# quotidiens et la différence de niveaux divergent.
#
# ⚠️ La première version relevait un jour sur SEPT : les seaux mensuels tombaient à
# 13 % de couverture, le plancher les vidait tous, et la figure dessinait 58 au lieu
# de 570. Le test échouait sur sa MISE EN SCÈNE, pas sur son sujet — et un garde qui
# échoue sur sa mise en scène finit relâché jusqu'à ce qu'il se taise.
_MEASURED = [d for i, d in enumerate(_DAYS) if i % 7 < 5]
_LEVELS = {"youtube": [(d, 1000 + i * 10) for i, d in enumerate(_MEASURED)]}
# La série QUOTIDIENNE ne porte que les écarts entre jours consécutifs : les deux
# journées sautées de chaque semaine sont perdues, et c'est tout le sujet.
_SERIES = {"youtube": [(d, 1) for d in _MEASURED]}


def _drawn(step: str) -> float:
    """La somme de ce que la figure dessine pour YouTube, au pas donné."""
    figs: dict = {}
    with patch("streamlit.plotly_chart", lambda f, **k: figs.setdefault("f", f)), \
         patch("streamlit.caption", lambda *a, **k: None), \
         patch("streamlit.info", lambda *a, **k: None), \
         patch("streamlit.markdown", lambda *a, **k: None):
        drawn = pc.render_platform_chart(
            _SERIES, since=_DAYS[0], until=_DAYS[-1], step=step, mode="absolute",
            cumulative=_LEVELS, key=f"grain_{step}")
    assert drawn, f"la figure ne s'est pas rendue au pas {step}"
    return sum(y for t in figs["f"].data if t.name and "YouTube" in t.name
               for y in (t.y or []) if y)


@pytest.mark.parametrize("step", ["week", "month"])
def test_every_grain_totals_the_same(step):
    """Le grain change la FORME de la courbe, jamais la quantité qu'elle porte."""
    reference = _drawn("month")
    got = _drawn(step)
    assert abs(got - reference) < max(1, reference * 0.01), (
        f"au pas « {step} » la figure totalise {got:,.0f} et au pas « mois » "
        f"{reference:,.0f}. Même plateforme, même période, deux réponses — et "
        "l'artiste ne choisit plus le grain, donc il voit ce nombre changer en "
        "déplaçant un filtre de période. La croissance d'un compteur se lit sur ses "
        "NIVEAUX à tous les pas ; la somme des écarts quotidiens jette tout ce qui "
        "s'est produit entre deux relevés espacés.")


def test_the_growth_read_is_the_real_one():
    """Non-vacuité : la mise en scène DOIT porter le défaut, sinon rien n'est gardé."""
    expected = _LEVELS["youtube"][-1][1] - _LEVELS["youtube"][0][1]
    assert abs(_drawn("month") - expected) < max(1, expected * 0.02), (
        f"la figure dessine {_drawn('month'):,.0f} pour une croissance de niveau de "
        f"{expected:,} : le garde ci-dessus comparerait deux nombres également faux")
    # Et la somme des écarts QUOTIDIENS, elle, est bien plus petite — sans quoi les
    # deux méthodes se vaudraient et la mutation ne pourrait pas rougir.
    daily = sum(v for _dd, v in _SERIES["youtube"])
    assert daily < expected / 5, (
        f"la somme des écarts quotidiens ({daily}) n'est pas nettement inférieure à "
        f"la croissance de niveau ({expected}) : les deux méthodes se valent dans "
        "cette mise en scène, donc la mutation qui rétablit l'ancienne ne pourrait "
        "pas rougir. Il faut un compteur à TROUS pour que le défaut existe.")


class _Col:
    def container(self, **_k):
        return nullcontext()


def test_a_lifetime_counter_says_what_the_curve_cannot_draw():
    """118 336 dans la boîte, 304 sur la courbe — l'écart se nomme."""
    seen: list = []

    def _rec(label, value, delta=None, help=None, **_k):   # noqa: A002
        seen.append((str(label), str(value), delta, str(help or "")))

    side = {"observed_growth": {"youtube": (_d.date(2025, 11, 29), 304)}}
    with patch("streamlit.markdown", lambda *a, **k: None), \
         patch("streamlit.caption", lambda *a, **k: None), \
         patch("streamlit.columns", lambda n, **k: [_Col() for _ in range(
             n if isinstance(n, int) else len(n))]), \
         patch("streamlit.metric", _rec):
        _render_tiles({"youtube": 118_336}, 118_336, 0, side=side)

    box = next((r for r in seen if "YouTube" in r[0]), None)
    assert box, f"la boîte YouTube a disparu : {[r[0] for r in seen]}"
    assert "29/11/25" in box[3], (
        f"l'infobulle ne dit pas depuis quand nous relevons ce compteur : {box[3]!r}. "
        "Sans cette date, l'écart entre 118 336 dans la boîte et 304 sur la courbe "
        "n'a aucune explication visible, et c'est lui qui fait dire « ces chiffres "
        "disent n'importe quoi ».")
    assert "304" in box[3], (
        f"l'infobulle ne dit pas ce que nous avons VU croître : {box[3]!r}")


def test_the_daily_exception_is_the_only_one():
    """Le pas du jour est la SEULE exception, et elle est délibérée.

    J'ai essayé de la supprimer le 2026-09-13, pour que tous les grains totalisent
    le même nombre. Deux gardes ont refusé :

      * entre deux relevés espacés de trente jours, attribuer tout l'écart au jour
        du second INVENTE un pic — on sait COMBIEN, jamais QUEL JOUR ;
      * la série de niveaux n'a pas de trous (report en avant), donc la figure
        perdait ses bandes hachurées et retombait au zéro inventé.

    L'écart entre 138 et 304 est donc le PRIX de l'honnêteté au grain fin, pas une
    incohérence à supprimer — et il est nommé à l'écran par la note « écoutes
    mesurées mais non traçables », qui ne s'affiche que dans ce cas précis.

    Ce que ce test tient : qu'il n'y ait pas d'exception DE PLUS. Une seconde
    condition de grain rétablirait des réponses multiples sans que personne le voie.
    """
    fn = next(n for n in ast.walk(ast.parse(_CHART.read_text(encoding="utf-8")))
              if isinstance(n, ast.FunctionDef) and n.name == "render_platform_chart")
    served = [n for n in ast.walk(fn) if isinstance(n, ast.Assign)
              and any(getattr(t, "id", "") == "served" for t in n.targets)]
    assert served, "`served` n'est plus affecté dans `render_platform_chart`"
    grains = {c.value for n in served for c in ast.walk(n.value)
              if isinstance(c, ast.Constant) and c.value in ("day", "week", "month",
                                                             "year")}
    assert grains == {"day"}, (
        f"les grains qui font exception sont {sorted(grains)} — il ne doit y en "
        "avoir qu'un, « day », et sa raison est écrite dans `platform_chart.py`. "
        "Chaque exception de plus est une réponse de plus à la même question.")
