"""Une ventilation qui ne couvre pas tout le dit, et le mesure.

Type: Test
Uses: pandas, un faux handle (aucune base)
Depends on: src/dashboard/views/meta_breakdowns.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Balayage croisé du 2026-09-11, artiste 1 en production : la dépense Meta vaut
**3 088 €** sur `meta_insights_performance_day`, et **2 348 €** seulement dans la
ventilation par pays — **76 %**. Les ventilations par âge et par placement tombent
sur la même part (75,7 %).

Ce n'est pas notre défaut : Meta n'attribue pas toute la dépense à une dimension,
les impressions dont il ignore le pays n'existent dans aucune ligne du breakdown.
Ce qui SERAIT notre défaut, c'est de ne pas le dire — le lecteur qui additionne les
barres trouve 740 € de moins que le chiffre de l'onglet d'à côté. Ce dépôt a payé
trois fois le même soir pour deux nombres sans explication.

La part est RECALCULÉE à chaque rendu et jamais écrite en dur : elle dépend du
compte, de la campagne et de la période collectée. Une constante deviendrait fausse
à la première nouvelle campagne — c'est la leçon que ce dépôt appelle « épingler la
distribution, jamais la constante ».
"""
from __future__ import annotations

import pytest


@pytest.fixture
def rendered(monkeypatch):
    """Appelle `_render_coverage` et renvoie les légendes écrites.

    Aucune base : le total voyage désormais dans une COLONNE du dataframe, en
    sous-requête scalaire de la requête du breakdown. C'est le cliquet
    d'allers-retours qui l'a imposé — une note explicative ne vaut pas un aller-retour
    de plus sur le chemin chaud — et ça rend ce garde plus simple qu'avant.
    """
    import pandas as pd

    from src.dashboard.views import meta_breakdowns as mb

    written: list[str] = []
    monkeypatch.setattr(mb.st, "caption", lambda text, *a, **k: written.append(str(text)))

    def run(shown: float, total: float):
        written.clear()
        mb._render_coverage(pd.DataFrame({"spend": [shown], "_spend_total": [total]}))
        return list(written)

    return run


def test_a_partial_breakdown_names_its_share(rendered) -> None:
    said = rendered(2348.0, 3087.82)
    assert said, "la ventilation ne couvre que 76 % de la dépense et ne le dit pas"
    note = said[0]
    assert "76" in note, f"la part n'est pas nommée : {note}"
    assert "2" in note and "3" in note, f"les deux montants ne sont pas dits : {note}"


def test_a_complete_breakdown_stays_silent(rendered) -> None:
    """Une note qui s'affiche toujours devient du bruit, et on cesse de la lire.

    Le seuil est à 0,5 % : Meta rend des centimes, et une note qui annonce « 100 % »
    sur un écart d'arrondi apprendrait au lecteur à l'ignorer le jour où elle dit 76.
    """
    assert not rendered(3087.82, 3087.82)
    assert not rendered(3086.0, 3087.82), "0,06 % d'écart n'est pas une lacune"


def test_no_data_at_all_says_nothing_rather_than_zero_percent(rendered) -> None:
    """« 0 % » sur une page vide se lirait comme une panne de collecte."""
    assert not rendered(0.0, 3087.82)
    assert not rendered(2348.0, 0.0)


def test_the_share_is_measured_and_not_written_down() -> None:
    """Une part en dur serait fausse à la première campagne.

    Le garde lit la STRUCTURE : la fonction doit diviser deux valeurs lues, pas
    formater un nombre littéral. `76` ne doit apparaître nulle part dans son corps.
    """
    import ast
    import inspect

    from src.dashboard.views import meta_breakdowns as mb

    src = inspect.getsource(mb._render_coverage)
    tree = ast.parse(src.lstrip())
    literals = [n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
                and n.value not in (0, 1, 100, 0.995)]
    assert not literals, (
        f"des nombres littéraux dans le calcul de la part : {literals}. Elle doit "
        "être divisée à chaque rendu, pas écrite.")
    assert any(isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)
               for n in ast.walk(tree)), "la part n'est plus calculée par une division"


def test_the_query_and_the_note_agree_on_the_column_name() -> None:
    """Renommer la colonne d'un côté fait disparaître la note SANS erreur.

    `_render_coverage` sort silencieusement quand `_spend_total` manque — c'est
    voulu : une note absente vaut mieux qu'une page morte. Mais ce silence rend le
    renommage indétectable. Vérifié le 2026-09-11 en renommant la colonne dans la
    requête : la page rendait ses deux figures, sans la note, sans une erreur, et
    aucun test ne rougissait.

    Les deux extrémités sont donc épinglées ensemble : la requête doit produire le
    nom que la note lit.
    """
    import inspect

    from src.dashboard.views import meta_breakdowns as mb

    page = inspect.getsource(mb)
    produced = page.count("_spend_total")
    assert produced >= 2, (
        f"`_spend_total` n'apparaît que {produced} fois : la requête et la note ne "
        "parlent plus de la même colonne, et la note disparaîtra en silence.")
    assert "AS _spend_total" in page, (
        "la requête ne produit plus la colonne `_spend_total` — la note ne sortira "
        "jamais, et rien ne le dira")
    assert '"_spend_total"' in inspect.getsource(mb._render_coverage), (
        "la note ne lit plus `_spend_total`")
