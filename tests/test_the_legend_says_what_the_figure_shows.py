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

Ce que ce garde exige depuis le 2026-09-12
------------------------------------------
`t_trend_caption` a été retirée, et ce fichier a été RETOURNÉ plutôt que supprimé.

Il exigeait que la légende soit dérivée du pas effectif. Elle l'était, et elle restait
du texte qui paraphrase un pixel : « une interruption veut dire qu'on n'a pas de
mesure — pas que le compteur est retombé » décrit exactement ce que la bande hachurée
dessine désormais. « Supprime-moi le texte inutile » (2026-09-12).

La même exigence porte donc maintenant sur les DEUX surfaces qui ont pris le relais,
et c'est ce qui rend le retournement légitime plutôt qu'un abandon :

  * le PAS et le MODE se lisent sur une barre visible au-dessus de la figure, pas
    dans un menu replié — et la barre montre le pas RÉELLEMENT appliqué ;
  * l'absence de mesure se lit sur la bande hachurée et son entrée de légende, et
    **aucune légende ne la reformule en prose**.

Le reste des tests est inchangé : ils portaient sur le sous-titre, les facettes et les
constantes mortes, et rien de tout cela n'a bougé.
"""
from __future__ import annotations

import ast
import itertools
from functools import lru_cache
from pathlib import Path

import pytest

from src.dashboard.utils.platform_chart import (
    MODES, _FINER_STEPS, _STEP_BUCKETS, _STEP_UNITS)

ROOT = Path(__file__).resolve().parents[1]
_STEPS = ("day", "week", "month", "year")


@lru_cache(maxsize=2)
def _tree(rel: str) -> ast.Module:
    """Lu à l'appel, pas à l'import — le test reste collectable sans sa cible."""
    return ast.parse((ROOT / rel).read_text(encoding="utf-8"))


def _home_call(name: str) -> list[ast.Call]:
    """Les appels à `st.<name>` dans `_render_trend`, lus dans l'arbre."""
    fn = next(n for n in ast.walk(_tree("src/dashboard/views/home.py"))
              if isinstance(n, ast.FunctionDef) and n.name == "_render_trend")
    return [n for n in ast.walk(fn)
            if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == name]


def test_the_step_and_the_mode_are_chosen_on_a_visible_bar() -> None:
    """« Voir toutes les possibilités direct » — pas replié dans un menu.

    Le filtre de période juste au-dessus est déjà une barre (`date_range.py`). Deux
    widgets voisins qui font la même chose sous deux formes différentes se lisent
    comme deux natures de réglage.
    """
    bars = _home_call("segmented_control")
    assert len(bars) >= 2, (
        f"{len(bars)} barre(s) dans `_render_trend` — il en faut deux, le mode et le "
        "pas. Un `st.selectbox` replie les options : l'artiste ne sait pas qu'elles "
        "existent.")
    dropdowns = _home_call("selectbox")
    assert not dropdowns, (
        f"{len(dropdowns)} menu(s) déroulant(s) sont revenus dans `_render_trend` "
        f"(lignes {[n.lineno for n in dropdowns]}).")


def test_the_bar_offers_a_step_the_figure_can_actually_draw() -> None:
    """Une case qui ne produit rien se lit comme une panne.

    Le pas `month` n'existait nulle part dans la figure jusqu'au 2026-09-12 ; le
    proposer sans l'implémenter aurait rendu la figure vide sur un clic.
    """
    fn = next(n for n in ast.walk(_tree("src/dashboard/views/home.py"))
              if isinstance(n, ast.FunctionDef) and n.name == "_render_trend")
    steps = next(
        (n for n in ast.walk(fn) if isinstance(n, ast.Assign)
         and any(getattr(t, "id", "") == "steps" for t in n.targets)), None)
    assert steps is not None and isinstance(steps.value, ast.Dict), (
        "`_render_trend` ne déclare plus le dictionnaire `steps` — la barre de pas "
        "est construite ailleurs et ce garde ne voit plus rien")
    offered = {k.value for k in steps.value.keys if isinstance(k, ast.Constant)}
    assert offered == set(_STEPS), (
        f"la barre propose {sorted(offered)} ; les quatre grains demandés le "
        f"2026-09-12 sont {sorted(_STEPS)}")
    unknown = offered - set(_FINER_STEPS) - {"day"}
    assert not unknown, (
        f"pas(s) proposé(s) que la figure ne sait pas agréger : {sorted(unknown)}. "
        "Cliquer la case rendrait une figure vide, ce qui se lit comme une panne.")


def test_the_day_is_the_default_unless_the_window_is_long() -> None:
    """Réglé « sur journalier par défaut » — sans rendre 1 400 points par plateforme."""
    home = (ROOT / "src/dashboard/views/home.py").read_text(encoding="utf-8")
    tree = ast.parse(home)
    ceiling = next(
        (n.value.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
         and any(getattr(t, "id", "") == "_DAY_UNTIL_DAYS" for t in n.targets)
         and isinstance(n.value, ast.Constant)), None)
    assert isinstance(ceiling, int) and 30 <= ceiling <= 400, (
        f"`_DAY_UNTIL_DAYS` vaut {ceiling!r} — un plafond hors de portée rend le "
        "défaut soit toujours jour (illisible sur 4 ans), soit jamais jour.")
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_render_trend")
    src = ast.unparse(fn)
    assert "_DAY_UNTIL_DAYS" in src and "'day'" in src, (
        "`_render_trend` ne compare plus la fenêtre à `_DAY_UNTIL_DAYS` — le défaut "
        "n'est plus dérivé de la période affichée")


def test_no_caption_reformulates_what_the_hatch_already_draws() -> None:
    """La bande hachurée dit l'absence en pixels ; la redire en prose est du bruit.

    C'est l'exigence qui a remplacé « la légende nomme son pas ». Elle est plus forte,
    pas plus faible : une légende juste restait une légende de trop.
    """
    import src.dashboard.utils.platform_chart as pc
    for gone in ("t_trend_caption", "t_missing"):
        assert not hasattr(pc, gone), (
            f"`{gone}` est revenue. Elle paraphrase la bande hachurée : les deux "
            "disent « ici on n'a pas mesuré », l'une en pixels au bon endroit de "
            "l'axe, l'autre en prose sous la figure.")
    assert hasattr(pc, "unmeasured_spans") and hasattr(pc, "_hatch_traces"), (
        "la hachure a disparu sans que la phrase revienne : l'absence n'est plus "
        "dite nulle part, ce qui est le défaut d'origine.")


@pytest.mark.parametrize("last_offset,expected", [
    # dernière mesure AVANT la fenêtre → « rien sur cette période »
    (-120, "trend_nothing_in_window"),
    # dernière mesure DANS la fenêtre → le compte est simplement jeune
    (-3, "trend_no_series"),
])
def test_an_empty_window_is_not_called_a_missing_history(
        monkeypatch, last_offset, expected) -> None:
    """« Pas encore assez d'historique » à un locataire qui en a quatre ans.

    Vu au navigateur le 2026-09-12 sur « 90 jours · Jour · Par période », et
    invisible en lisant le code : le CSV Spotify n'avait pas été déposé depuis 92
    jours, donc la fenêtre était vide — et l'écran l'annonçait comme une jeunesse de
    compte. Les deux silences demandent des GESTES OPPOSÉS : le premier fait
    attendre, le second demande un import.

    ⚠️ Ce test est BEHAVIOURAL et sa première version ne l'était pas : elle lisait
    l'arbre de `_render_trend` et vérifiait que les deux clés et `since` y
    apparaissaient. Avec la condition remplacée par `if False:`, elle est restée
    VERTE — un prédicat sans site, la cinquième forme d'aveuglement de ce dépôt.
    On rend donc vraiment la section et on lit le message écrit.
    """
    import datetime as _d

    from src.dashboard.views import home as hv

    said: list[str] = []
    today = _d.date(2026, 9, 12)
    since, until = today - _d.timedelta(days=90), today
    series = {"spotify": [(today + _d.timedelta(days=last_offset), 10)]}

    monkeypatch.setattr(hv.st, "info", lambda text, *a, **k: said.append(str(text)))
    monkeypatch.setattr(hv.st, "warning", lambda text, *a, **k: said.append(str(text)))
    monkeypatch.setattr(hv.st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(hv.st, "subheader", lambda *a, **k: None)
    monkeypatch.setattr(hv.st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(hv.st, "segmented_control",
                        lambda label, options, **k: k.get("default"))
    monkeypatch.setattr(hv.st, "columns",
                        lambda spec, **k: [_Silent() for _ in
                                           (spec if isinstance(spec, list)
                                            else range(spec))])
    # La figure ne dessine rien : c'est l'hypothèse du test, et le module de la
    # figure a ses propres gardes pour savoir QUAND elle ne dessine rien.
    import src.dashboard.utils.platform_chart as pc
    monkeypatch.setattr(pc, "render_platform_chart", lambda *a, **k: False)

    hv._render_trend(None, series, since, until, "90d", 1)

    # On lit le TEXTE rendu, pas la clé : c'est ce que l'artiste a sous les yeux,
    # et c'est le niveau auquel le défaut a été vu.
    marks = {"trend_nothing_in_window": "Aucune mesure sur cette période",
             "trend_no_series": "Pas encore assez d'historique"}
    joined = " ".join(said)
    assert said, "la section ne dit RIEN quand la figure ne dessine pas"
    assert marks[expected] in joined, (
        f"dernière mesure à J{last_offset} : attendu « {marks[expected]}… », "
        f"écrit : {said}")
    unwanted = next(v for k, v in marks.items() if k != expected)
    assert unwanted not in joined, (
        f"dernière mesure à J{last_offset} : c'est le message de l'AUTRE silence "
        f"qui est écrit (« {unwanted}… »). Les deux demandent des gestes opposés — "
        "l'un fait attendre, l'autre demande un import.")


class _Silent:
    """Une colonne Streamlit qui n'affiche rien — juste un gestionnaire de contexte."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


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

    # ET LE VOCABULAIRE DOIT ÊTRE LU QUELQUE PART. Corriger la constante sans la
    # brancher serait « du code correct que rien n'atteint », déjà payé six fois ici.
    #
    # Les trois SOUS-TITRES qui la lisaient sont partis le 2026-09-12 (« redondant
    # avec le tableau […] on a déjà les valeurs sur les filtres »). Le mot survit là
    # où il compte encore des seaux : la ligne « Total » du récapitulatif, qui écrit
    # « 181 semaines » à côté du nombre. Le garde suit le lecteur, il ne disparaît pas
    # avec l'ancien.
    # LES DEUX FORMES D'ACCÈS, et ne compter que l'une est le défaut que ce garde
    # vient de commettre : `_STEP_BUCKETS[step]` est un `Subscript`, mais le
    # récapitulatif écrit `_STEP_BUCKETS.get(step, "points")`, un `Attribute`. Le
    # prédicat ne voyait que la première et a déclaré morte une constante lue.
    def _reads(node) -> bool:
        if isinstance(node, ast.Subscript):
            return getattr(node.value, "id", "") == "_STEP_BUCKETS"
        if isinstance(node, ast.Attribute):
            return getattr(node.value, "id", "") == "_STEP_BUCKETS"
        return False

    reading = sum(
        1 for rel in ("src/dashboard/utils/platform_chart.py",
                      "src/dashboard/utils/platform_chart_notes.py")
        for n in ast.walk(_tree(rel)) if _reads(n))
    assert reading >= 1, (
        "plus personne ne lit `_STEP_BUCKETS` : le vocabulaire des seaux est devenu "
        "une constante morte, et le prochain lecteur repartira sur « années »")


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
