"""Les notes sous la figure décrivent la figure AFFICHÉE, pas une autre.

Type: Test
Uses: platform_chart (sans Streamlit — les `st.caption` sont capturés), ast
Depends on: src/dashboard/utils/platform_chart.py, src/dashboard/views/home.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Signalé le 2026-09-11, APRÈS le déploiement du correctif de la couche or :
« je n'ai aucune data sur youtube depuis le début ». Mesuré dans le conteneur de
production le même soir, la figure traçait pourtant YouTube à **118 334**, à tous les
pas, avec le filtre « Depuis le début ». Ce n'était pas la figure qui mentait, c'était
la PROSE sous elle :

  * « Sur 181 semaines, certaines plateformes n'ont pas été mesurées partout
    (🎬 YouTube 26). **Leur aire s'interrompt là** » ;
  * « ⏸️ Écoutes mesurées mais **non traçables** : 🎬 YouTube 167 ».

Les deux étaient exactes tant que la courbe venait de la série QUOTIDIENNE. Depuis que
le mode cumulé lit la couche or, elles sont fausses : une plateforme à compteur n'a
plus de trou — entre deux relevés son niveau est connu — et les 167 vues « non
traçables » sont DANS la courbe, puisque le compteur les porte.

Une note qui décrit une autre figure que celle affichée est pire que pas de note : le
lecteur croit la prose plutôt que ses yeux. C'est la troisième fois que ce dépôt paie
un texte adressé à la mauvaise figure, et la première fois que le correctif d'un
défaut crée le suivant dans sa propre explication.
"""
from __future__ import annotations

import ast
import datetime as _d
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture
def notes():
    """Rend la figure hors Streamlit et renvoie la liste des légendes écrites."""
    from src.dashboard.utils import platform_chart as pc

    written: list[str] = []
    real_chart, real_caption = pc.st.plotly_chart, pc.st.caption
    pc.st.plotly_chart = lambda fig, **k: None
    pc.st.caption = lambda text, *a, **k: written.append(str(text))

    days = [_d.date(2026, 1, 1) + _d.timedelta(days=i) for i in range(60)]
    # YouTube mesurée UN jour sur cinq : la série quotidienne est pleine de trous,
    # et c'est exactement la situation où la note se trompait.
    series = {"spotify": [(d, 10) for d in days],
              "youtube": [(d, 3) for i, d in enumerate(days) if i % 5 == 0]}
    gold = {"youtube": [(days[0], 1000), (days[-1], 5000)]}

    def build(mode: str, with_gold: bool = True):
        written.clear()
        pc.render_platform_chart(series, since=days[0], until=days[-1], step="day",
                                 mode=mode, cumulative=(gold if with_gold else None),
                                 key="guard")
        return list(written)

    try:
        yield build
    finally:
        pc.st.plotly_chart, pc.st.caption = real_chart, real_caption


def test_a_platform_served_by_the_gold_layer_is_not_announced_as_interrupted(notes) -> None:
    """Sa courbe est continue : dire qu'elle s'interrompt fait lire une panne."""
    said = " ".join(notes("cumulative"))
    assert "YouTube" not in said, (
        "le mode cumulé annonce encore YouTube comme non mesurée, alors que sa courbe "
        "est continue — sa valeur est connue entre deux relevés. Notes écrites :\n"
        + "\n".join(notes("cumulative")))


def test_the_same_platform_IS_announced_when_the_daily_series_is_drawn(notes) -> None:
    """L'exemption ne vaut que pour le mode qui lit la couche or.

    Sans ce test, retirer la note partout serait vert — et « Par période » trace bien
    la série trouée, où l'aire s'interrompt vraiment.
    """
    said = " ".join(notes("absolute"))
    assert "YouTube" in said, (
        "le mode « Par période » trace la série quotidienne, pleine de trous, et ne "
        "le dit plus. Notes écrites :\n" + "\n".join(notes("absolute")))


def test_without_a_gold_series_the_cumulative_mode_still_warns(notes) -> None:
    """L'exemption suit la SOURCE, pas le mode.

    Une plateforme dont le cumul est reconstruit à partir des écarts quotidiens a
    bien des trous, en mode cumulé comme ailleurs.
    """
    said = " ".join(notes("cumulative", with_gold=False))
    assert "YouTube" in said, (
        "sans série de la couche or, le cumul est reconstruit à partir d'une série "
        "trouée : la note doit rester.")


def test_the_home_page_hides_the_discarded_note_in_cumulative_mode() -> None:
    """L'autre moitié du défaut, rendue par la vue et pas par le module.

    « Écoutes mesurées mais non traçables : YouTube 167 » est vrai de la conversion
    cumul → quotidien, et faux de la courbe cumulée, qui les porte.
    """
    home = (_ROOT / "src" / "dashboard" / "views" / "home.py").read_text(encoding="utf-8")
    tree = ast.parse(home)
    call = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.Call)
         and getattr(n.func, "id", "") == "discarded_deltas"), None)
    assert call is not None, "l'accueil n'appelle plus `discarded_deltas`"
    guarded = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.IfExp)
        and any(isinstance(c, ast.Constant) and c.value == "cumulative"
                for c in ast.walk(n.test))
        and any(x is call for x in ast.walk(n))
    ]
    assert guarded, (
        "l'appel à `discarded_deltas` n'est plus conditionné au mode : la note "
        "« non traçables » réapparaît sous une courbe qui, elle, les trace.")
