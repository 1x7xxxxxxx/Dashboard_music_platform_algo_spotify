"""Un verdict ne se prononce pas sur une courbe que personne n'a encore rapportée.

Type: Test
Uses: pytest, ast
Depends on: src/dashboard/views/trigger_algo/_tab_budget_roi.py
Persists in: nothing

Ce qui a été mesuré (2026-09-10)
--------------------------------
La figure « breakeven » compare deux cumuls en euros : la dépense Meta, quotidienne, et
le revenu du distributeur, mensuel. La frise court du premier au dernier jour des DEUX
séries réunies, et les trous sont comblés par des zéros.

Ces zéros sont justes AU MILIEU d'une série — un jour sans dépense publicitaire a bien
dépensé zéro. Ils sont faux APRÈS la fin : celle des deux qui s'arrête la première
continue alors en ligne plate, non pas parce qu'elle vaut zéro sur cette période, mais
parce que personne ne l'a encore rapportée.

Mesuré pour l'artiste 1 : la dépense Meta s'arrête au **2024-09-30**, le revenu continue
**458 jours** de plus. Sur ces 458 jours, un cumul monte pendant que l'autre est figé :
le croisement est garanti par construction. Et sur ce croisement, la page affichait
« ✅ Breakeven atteint le … » — un verdict, en vert, sur une comparaison qui n'en est
plus une.

Même famille que le compteur cumulé qui retombe à zéro après sa dernière mesure : après
le dernier relevé, on ne sait pas, et « on ne sait pas » ne se dessine pas comme une
valeur.

Ce que ce fichier garde
-----------------------
Le verdict est borné au RECOUVREMENT — la fenêtre où les deux séries existent — et la
période au-delà est nommée, à l'écrit comme sur la figure. Ce n'est pas le calcul qui
change de nature : c'est sa portée qui devient dite. Un « non atteint » qui ne dit pas
jusqu'où il regarde se lit comme un constat définitif.
"""
from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_REL = "src/dashboard/views/trigger_algo/_tab_budget_roi.py"


@lru_cache(maxsize=1)
def _tree() -> ast.Module:
    """Lu à l'appel, pas à l'import : le fichier de test reste collectable sans sa cible."""
    return ast.parse((ROOT / _REL).read_text(encoding="utf-8"))


def _assigned_names() -> set[str]:
    return {t.id for n in ast.walk(_tree()) if isinstance(n, ast.Assign)
            for t in n.targets if isinstance(t, ast.Name)}


def test_the_overlap_is_computed_from_both_series() -> None:
    """Sans borne commune, la fenêtre du verdict est celle de la plus longue des deux."""
    assert "covered_end" in _assigned_names(), (
        "la borne de recouvrement a disparu : le verdict de breakeven repart sur toute "
        "la frise, donc sur la portion où l'une des deux courbes est une ligne plate "
        "fabriquée. Pour l'artiste 1, cela représente 458 jours où le croisement est "
        "garanti par construction.")
    # Et elle doit être un MINIMUM des deux fins — un maximum ne bornerait rien.
    for node in ast.walk(_tree()):
        if (isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "covered_end"
                        for t in node.targets)):
            assert (isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == "min"), (
                "`covered_end` n'est plus le MINIMUM des deux fins de série. Un maximum "
                "rendrait la borne inopérante tout en ayant l'air d'un correctif.")
            break


def test_the_breakeven_search_is_restricted_to_the_overlap() -> None:
    """Le calcul doit LIRE la borne, pas seulement la poser à côté."""
    src = (ROOT / _REL).read_text(encoding="utf-8")
    tree = ast.parse(src)
    guarded = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        body = ast.dump(ast.Module(body=node.body, type_ignores=[]))
        if "breakeven_date" not in body:
            continue
        if "covered_end" in ast.dump(node.iter):
            guarded = True
    assert guarded, (
        "la boucle qui cherche la date de breakeven ne filtre plus sur `covered_end` : "
        "la borne est calculée et ignorée, ce qui est pire qu'absente — elle donne "
        "l'apparence d'un correctif.")


def test_the_uncovered_window_is_named_not_merely_cropped() -> None:
    """Un verdict borné en silence se lit comme un verdict définitif."""
    src = (ROOT / _REL).read_text(encoding="utf-8")
    assert "trigger_algo.roi.breakeven_window" in src, (
        "la légende qui dit jusqu'où porte le verdict a disparu. Recadrer sans le dire "
        "laisse un « non atteint » se lire comme un constat définitif, alors qu'il ne "
        "porte que sur la fenêtre où les deux séries existent.")
    assert "add_vrect" in src, (
        "la zone non couverte n'est plus distinguée sur la figure. Le lecteur doit "
        "VOIR où la comparaison cesse d'en être une — c'est la moitié du correctif que "
        "le texte seul ne fait pas.")


def test_the_note_is_translated() -> None:
    """Une clé sans entrée anglaise rend la clé brute à l'écran."""
    catalog = (ROOT / "src/dashboard/utils/i18n_catalog/trigger_algo.py").read_text(
        encoding="utf-8")
    for key in ("trigger_algo.roi.breakeven_window",
                "trigger_algo.roi.one_series_only"):
        assert key in catalog, f"`{key}` n'a pas d'entrée EN — la clé s'afficherait brute"
