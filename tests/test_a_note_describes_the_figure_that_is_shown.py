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

    # (mesuré, total, écarté) — la forme que `discarded_deltas` rend.
    discarded = {"youtube": (12, 400, 167)}

    def build(mode: str, with_gold: bool = True, step: str = "day"):
        written.clear()
        pc.render_platform_chart(series, since=days[0], until=days[-1], step=step,
                                 mode=mode, cumulative=(gold if with_gold else None),
                                 discarded=discarded, key="guard")
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


# `test_the_home_page_hides_the_discarded_note_in_cumulative_mode` vivait ici. Il
# tenait une vraie propriété — la note « non traçables » ne doit pas s'afficher sous
# une figure qui compte ces écoutes — mais il la tenait AU MAUVAIS ENDROIT : il
# vérifiait que l'accueil conditionnait l'appel au mode.
#
# La note a déménagé dans `platform_chart` le 2026-09-11, parce que la condition ne
# pouvait pas être écrite depuis la vue : elle dépend aussi du PAS RETENU, que seul le
# module connaît quand l'utilisateur a choisi « Automatique ». Le retirer d'ici n'est
# donc pas un assouplissement — les deux tests ci-dessous tiennent la même propriété
# sur les quatre combinaisons de mode et de pas, et sur l'emplacement lui-même.


def test_the_discarded_note_only_speaks_where_the_daily_deltas_are_drawn(notes) -> None:
    """« Écoutes non traçables » est vrai du pas QUOTIDIEN, et faux au-delà.

    Depuis qu'un seau plus large qu'un jour porte la CROISSANCE du compteur — niveau
    de fin moins niveau de fin du seau précédent — ces écoutes sont dans la figure dès
    le pas hebdomadaire. Les y annoncer perdues est le même défaut que celui de ce
    fichier, dans l'autre sens.
    """
    assert any("non traçables" in n for n in notes("absolute", step="day")), (
        "au pas du JOUR la note doit rester : l'écart entre deux relevés distants "
        "n'est attribuable à aucune journée, et il n'est donc pas tracé")
    for mode, step in (("absolute", "week"), ("absolute", "year"),
                       ("cumulative", "day"), ("cumulative", "week")):
        said = notes(mode, step=step)
        assert not any("non traçables" in n for n in said), (
            f"mode={mode} pas={step} annonce des écoutes non traçables alors que la "
            f"figure les compte. Notes : {said}")


def test_the_note_lives_where_the_resolved_step_is_known() -> None:
    """Elle ne peut pas être juste depuis la vue, et ce n'est pas un détail de style.

    L'accueil connaît le pas DEMANDÉ ; « Automatique » n'en est pas un. Seul le module
    sait lequel a été retenu — il descend même d'un cran quand le pas demandé ne
    produit qu'un seul seau. Une note rendue depuis la vue se trompe donc exactement
    dans les cas où le pas a été choisi pour elle. C'est l'argument qui avait déjà
    fait descendre `t_trend_caption` ici ; la note voisine était restée en haut.
    """

    home = (_ROOT / "src" / "dashboard" / "views" / "home.py").read_text(encoding="utf-8")
    tree = ast.parse(home)
    captions = [n for n in ast.walk(tree)
                if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "caption"]
    assert not [c for c in captions
                if any(isinstance(a, ast.Constant) and "trend_discarded" in str(a.value)
                       for a in ast.walk(c))], (
        "l'accueil rend de nouveau la note lui-même : elle se trompera dès que le pas "
        "sera « Automatique »")
    assert any(k.arg == "discarded"
               for n in ast.walk(tree) if isinstance(n, ast.Call)
               for k in n.keywords), (
        "l'accueil ne passe plus `discarded` à la figure : la note a disparu au lieu "
        "de déménager, et ce qui manque n'est plus dit nulle part")


def test_no_note_contradicts_what_the_figure_shows(notes) -> None:
    """La propriété générale, au lieu d'une note à la fois.

    Trois notes de ce module nomment une plateforme pour dire qu'il lui manque
    quelque chose, et chacune affirme une chose PRÉCISE :

      * « n'apparaît pas à ce pas » — elle n'a aucune trace. Faux si elle est tracée.
      * « son aire s'interrompt » — sa bande ne couvre pas tout l'axe. Faux si elle
        le couvre entièrement.
      * « écoutes non traçables » — la figure montre les écarts quotidiens, donc
        seulement au pas du JOUR et hors mode cumulé.

    Les trois ont été corrigées séparément le 2026-09-11, et la troisième n'a été
    trouvée que parce que la mutation d'une autre l'a fait apparaître dans sa sortie.
    Ce test pose la question une fois pour toutes, sur les six combinaisons de mode et
    de pas — et il vérifie CHAQUE phrase contre ce que la figure montre vraiment,
    plutôt que d'interdire en bloc de nommer une plateforme tracée. La première
    version le faisait, et elle refusait « s'interrompt » sur une bande qui
    s'interrompt réellement : au pas du jour, YouTube est tracée ET trouée, les deux
    en même temps.
    """
    from src.dashboard.utils import platform_chart as pc

    for mode in ("cumulative", "absolute"):
        for step in ("day", "week", "year"):
            captured = {}
            real = pc.st.plotly_chart
            pc.st.plotly_chart = lambda fig, **k: captured.__setitem__("fig", fig)
            try:
                said = notes(mode, step=step)
            finally:
                pc.st.plotly_chart = real
            fig = captured.get("fig")
            if fig is None:
                continue

            axis = {x for t in fig.data for x in t.x}
            covered: dict = {}
            for t in fig.data:
                covered.setdefault(t.name, set()).update(t.x)
            where = f"mode={mode} pas={step}"

            for label, xs in covered.items():
                for note in said:
                    if label not in note:
                        continue
                    if "n'apparaît pas" in note:
                        raise AssertionError(
                            f"{where} : « {label} » est TRACÉE et la note dit qu'elle "
                            f"n'apparaît pas.\n  {note[:160]}")
                    if "s'interrompt" in note and xs >= axis:
                        raise AssertionError(
                            f"{where} : « {label} » couvre tout l'axe et la note dit "
                            f"que son aire s'interrompt.\n  {note[:160]}")
                    if ("non traçables" in note
                            and not (step == "day" and mode == "absolute")):
                        raise AssertionError(
                            f"{where} : la note annonce des écoutes non traçables "
                            f"alors que la figure les compte.\n  {note[:160]}")
