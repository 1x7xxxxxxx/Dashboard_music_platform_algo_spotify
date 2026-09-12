"""Une rupture de méthode ne devient pas une quantité, et la figure s'étiquette.

Type: Test
Uses: pytest, platform_timeseries.level_discontinuities, platform_chart
Depends on: src/dashboard/utils/platform_chart.py, src/dashboard/views/home.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Signalé le 2026-09-12 : « j'ai un pic à 18000 pour youtube alors que c'est faux ».
Mesuré en production, artiste 1 : le niveau YouTube passe de 99 778 à 118 216 entre le
10 et le 11 juin 2026 — **+18 438 en une nuit**, quand le plus gros écart quotidien de
toute la série vaut **7** et sa médiane **1**.

Le 11 juin, la collecte a changé de DÉFINITION : du compteur de CHAÎNE, qui plafonnait
à 99 xxx et comptait des vidéos qui ne sont pas les siennes (prouvé ~10× faux le
2026-09-08), à la somme des compteurs PAR VIDÉO. La marche est réelle dans les données
et fausse comme quantité — personne n'a fait 18 438 vues ce jour-là.

LE SEUIL EST MESURÉ, et ce fichier en garde la mesure. Balayé sur les cinq séries de
compteur de la production, chacune comparant son plus gros écart à son 95ᵉ centile :

    a1 youtube 1 676 · a1 soundcloud 20,4 · a12 soundcloud 3,0
    a14 youtube 1,5 · a14 soundcloud 1,4

Une seule sort, et c'est la rupture connue. Le creux entre 20,4 et 1 676 est large ;
100 y est 5× au-dessus de la plus forte croissance LÉGITIME du parc et 16× sous la
rupture. Un seuil hors de ce creux rend le détecteur soit aveugle, soit destructeur —
il effacerait la première vraie poussée d'un artiste.

Mutations vues rouges avant écriture (2026-09-12) :
  * `_DISCONTINUITY_RATIO` porté à 5 000 → test_the_known_production_break_is_caught
    ÉCHOUE ;
  * ramené à 5 → test_a_real_surge_is_never_called_a_break ÉCHOUE en nommant le
    rapport 20,4 de a1/soundcloud ;
  * `_DISCONTINUITY_MIN_POINTS` ramené à 2 → test_a_short_series_is_never_judged
    ÉCHOUE ;
  * le seau enjambant la rupture rendu `0` au lieu de `None` →
    test_the_bucket_that_spans_a_break_is_unmeasured_not_zero ÉCHOUE.
"""
from __future__ import annotations

import ast
import datetime as _d
from pathlib import Path

import pytest

from src.dashboard.utils.platform_timeseries import (
    _DISCONTINUITY_MIN_POINTS, _DISCONTINUITY_RATIO, level_discontinuities,
)

_HOME = Path(__file__).resolve().parents[1] / "src/dashboard/views/home.py"
_CHART = Path(__file__).resolve().parents[1] / "src/dashboard/utils/platform_chart.py"


def _series(daily: int, n: int, jump: int = 0, at: int = -1) -> list:
    """Une série de niveaux qui monte de `daily` par jour, avec un saut optionnel."""
    day, level, out = _d.date(2026, 1, 1), 100_000, []
    for i in range(n):
        level += daily + (jump if i == at else 0)
        out.append((day + _d.timedelta(days=i), level))
    return out


# ── LE SEUIL, CONTRE LES CHIFFRES RÉELS DE LA PRODUCTION ────────────────────

def test_the_known_production_break_is_caught():
    """La rupture du 2026-06-11 sort à un rapport de 1 676 — elle doit être vue."""
    rows = _series(daily=1, n=70, jump=18_438, at=40)
    found = level_discontinuities(rows)
    assert found, (
        f"la rupture de +18 438 sur une série dont l'écart courant vaut 1 n'est pas "
        f"détectée (rapport {_DISCONTINUITY_RATIO}). C'est le pic signalé le "
        "2026-09-12, et il repart en production en « Par période ».")
    assert max(found.values()) >= 18_438


def test_a_real_surge_is_never_called_a_break():
    """La plus forte croissance LÉGITIME du parc vaut 20,4× son 95ᵉ centile."""
    # a1/soundcloud, mesuré le 2026-09-12 : p95 = 8, max = 163.
    rows = _series(daily=8, n=60, jump=163 - 8, at=30)
    assert not level_discontinuities(rows), (
        "une poussée réelle de 163 sur une série à 8 par jour — a1/soundcloud, "
        f"rapport 20,4 — est déclarée rupture au seuil {_DISCONTINUITY_RATIO}. Le "
        "détecteur effacerait de vraies écoutes de la figure, ce qui est pire que le "
        "défaut qu'il corrige.")


def test_the_threshold_sits_in_the_measured_gap():
    """Entre 20,4 (plus forte croissance légitime) et 1 676 (la rupture)."""
    assert 20.4 < _DISCONTINUITY_RATIO < 1676, (
        f"`_DISCONTINUITY_RATIO` vaut {_DISCONTINUITY_RATIO}, hors du creux mesuré "
        "le 2026-09-12 sur les cinq séries de compteur de la production. En dessous "
        "de 20,4 le détecteur efface de vraies poussées ; au-dessus de 1 676 il rate "
        "la rupture qui l'a fait écrire.")


def test_a_short_series_is_never_judged():
    """Sur cinq points, un 95ᵉ centile ne veut rien dire."""
    rows = _series(daily=1, n=4, jump=99_999, at=2)
    assert not level_discontinuities(rows), (
        f"une série de 4 points est jugée alors que le plancher est "
        f"{_DISCONTINUITY_MIN_POINTS}. La première vraie poussée d'un artiste neuf "
        "serait déclarée « rupture de méthode » et effacée de sa figure.")


# ── CE QUE LA FIGURE EN FAIT ────────────────────────────────────────────────

def test_the_levels_are_rebased_at_the_source():
    """La correction vit dans `cumulative_by_platform`, et nulle part ailleurs.

    ── LA PREMIÈRE VERSION ÉTAIT FAUSSE, ET UN GARDE L'A DIT ────────────────────

    Elle soustrayait le saut des totaux et blanchissait le seau de la figure —
    **deux corrections, deux surfaces**. `test_a_bounded_total_on_a_counter_is_a_
    difference_of_levels` a mesuré le résultat : le total borné rendait **187**
    pendant que la courbe montait de **18 625** sur la même fenêtre. Deux nombres
    pour la même question sur le même écran, ce qu'ADR-019 interdit, et exactement
    le défaut que le PDF imprimait sur une seule page.

    La bonne correction est en AMONT : recaler l'historique d'avant la rupture. Ce
    n'est pas inventer des vues — c'est cesser de mesurer avec le mauvais
    instrument. Les vidéos AVAIENT ces vues avant le 11 juin ; c'est le compteur de
    chaîne qui ne les voyait pas, et il est ~10× faux (prouvé le 2026-09-08).

    Mesuré en production après recalage : plus gros saut **82** au lieu de 18 438,
    niveau final **inchangé** (118 336), fenêtre enjambante **18 558 → 120**,
    fenêtre sans rupture **intacte** (75 → 75).
    """
    from src.dashboard.utils.platform_timeseries import cumulative_by_platform

    src = (Path(__file__).resolve().parents[1]
           / "src/dashboard/utils/platform_timeseries.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    # ⚠️ LES TROIS LECTURES, PAS UNE. Le PDF et la vue YouTube n'appellent pas
    # `cumulative_by_platform` — ils lisent `youtube_cumulative_views` directement.
    # Ne recaler que la première laisserait le pic sur deux surfaces.
    for name in ("cumulative_by_platform", "youtube_cumulative_views",
                 "soundcloud_cumulative_plays"):
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == name)
        assert any(isinstance(n, ast.Call)
                   and getattr(n.func, "id", "") == "rebase_method_changes"
                   for n in ast.walk(fn)), (
            f"`{name}` ne passe pas par `rebase_method_changes`. Toute lecture d'une "
            "série de niveaux doit être corrigée au même endroit : corriger chaque "
            "surface séparément produit une figure et une tuile qui se contredisent "
            "— mesuré le 2026-09-12, 187 contre 18 625.")
    assert cumulative_by_platform(None, None) == {}


def test_the_rebase_preserves_the_lifetime_level():
    """Le niveau FINAL ne bouge pas d'une vue — seuls les antérieurs sont relevés."""
    from src.dashboard.utils.platform_timeseries import level_discontinuities

    rows = _series(daily=1, n=70, jump=18_438, at=40)
    breaks = level_discontinuities(rows)
    assert breaks
    rebased = list(rows)
    for day, jump in sorted(breaks.items()):
        rebased = [(d, v + jump if d < day else v) for d, v in rebased]
    assert rebased[-1][1] == rows[-1][1], (
        f"le recalage a changé le niveau final : {rebased[-1][1]} au lieu de "
        f"{rows[-1][1]}. Le total « depuis le début » est le compteur courant et il "
        "est JUSTE — c'est l'historique d'avant qui était mesuré autrement. Le "
        "déplacer casserait l'accord avec la couche or.")
    growths = [v1 - v0 for (_d0, v0), (_d1, v1) in zip(rebased, rebased[1:])]
    assert max(growths) < 18_438, (
        f"la marche survit au recalage : {max(growths)}. La série doit être continue "
        "après correction, sinon tout ce qui en dérive porte encore le pic.")


# ── LES DEUX MODES, ET LA LÉGENDE COMME FILTRE ──────────────────────────────

def test_the_mode_is_a_single_toggle_defaulting_to_cumulative():
    """« je veux uniquement le bouton cumulé allumé ou non » (2026-09-13).

    La barre a porté quatre modes, puis deux. Deux boutons dont l'un est toujours
    actif sont un interrupteur qui s'ignore — `st.toggle` dit la même chose en une
    case, et son état se lit sans comparer deux libellés.

    Ce garde vérifie les DEUX propriétés, parce qu'elles se perdent séparément : que
    ce soit bien un interrupteur, et qu'il soit ALLUMÉ par défaut. Le cumulé est le
    seul mode où toutes les plateformes sont visibles — éteint, YouTube pèse 0,18 %
    de la pile sur l'historique complet (mesuré en production le 2026-09-13) et
    disparaît sous le pixel.
    """
    tree = ast.parse(_HOME.read_text(encoding="utf-8"))
    toggles = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
               and getattr(n.func, "attr", "") == "toggle"]
    assert len(toggles) == 1, (
        f"{len(toggles)} `st.toggle` dans home.py — il en faut exactement un, celui "
        "du cumulé. Zéro : le mode est redevenu une barre ou a disparu. Plus d'un : "
        "un second réglage s'est glissé là où l'artiste en demandait un seul.")
    default = next((kw.value for kw in toggles[0].keywords if kw.arg == "value"), None)
    assert isinstance(default, ast.Constant) and default.value is True, (
        "l'interrupteur du cumulé n'est plus allumé par défaut. Éteint, la figure "
        "montre les gains PAR PAS : sur l'historique complet, la croissance observée "
        "de YouTube vaut 304 vues contre 165 065 pour Spotify — sa bande passe sous "
        "le pixel et l'artiste lit « pas de données ».")

    # ET LES QUATRE MODES NE DOIVENT PLUS ÊTRE OFFERTS NULLE PART dans cette vue.
    bars = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and getattr(n.func, "attr", "") == "segmented_control"]
    assert not bars, (
        f"une barre `segmented_control` subsiste dans home.py (lignes "
        f"{[n.lineno for n in bars]}) : le réglage du mode est redevenu un menu.")


def test_the_legend_is_the_only_source_filter():
    """Le `multiselect` n'existait qu'en mode « Part » — parti avec lui."""
    tree = ast.parse(_HOME.read_text(encoding="utf-8"))
    widgets = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
               and getattr(n.func, "attr", "") == "multiselect"]
    assert not widgets, (
        f"un `st.multiselect` subsiste dans `home.py` (lignes "
        f"{[n.lineno for n in widgets]}). « je voulais cette légende cliquable pour "
        "les sélectionner » — un clic de légende est côté navigateur et ne relance "
        "pas le script, là où le widget coûtait un rendu complet (287 ms mesurés).")


@pytest.mark.parametrize("mode", ["cumulative", "absolute"])
def test_each_platform_gets_exactly_one_label(mode):
    """Une étiquette par plateforme — pas un mur de chiffres sur 44 points."""
    import datetime as dt
    from unittest.mock import patch

    from src.dashboard.utils import platform_chart as pc

    day = dt.date(2026, 1, 1)
    series = {"spotify": [(day + dt.timedelta(days=i), 10 + i) for i in range(40)]}
    seen = {}

    with patch("streamlit.plotly_chart",
               lambda fig, **k: seen.setdefault("f", fig)), \
         patch("streamlit.caption", lambda *a, **k: None):
        assert pc.render_platform_chart(
            series, since=day, until=day + dt.timedelta(days=39),
            step="day", mode=mode, key=f"lab_{mode}")

    notes = list(seen["f"].layout.annotations or [])
    assert len(notes) == 1, (
        f"mode {mode} : {len(notes)} étiquette(s) pour UNE plateforme. Une par "
        "plateforme — l'infobulle donne déjà tous les points, un mur de chiffres "
        "rend la courbe illisible.")
    # En cumulé on étiquette la DERNIÈRE valeur (49), en par période le PIC (49
    # aussi ici, car la série monte) — le test de forme est le nombre, la valeur
    # exacte est gardée par la lecture du code ci-dessus.
    assert notes[0].text, "l'étiquette est vide"


# ── CE QUI A ÉTÉ RETIRÉ D'ICI, ET POURQUOI ──────────────────────────────────
#
# `test_a_window_that_spans_a_break_excludes_it` vérifiait que `platform_totals`
# SOUSTRAYAIT le saut. C'était la première version du correctif, et elle était
# fausse : elle corrigeait les totaux et la figure SÉPARÉMENT, donc les deux se
# contredisaient — 187 contre 18 625, mesuré par
# `test_a_bounded_total_on_a_counter_is_a_difference_of_levels`.
#
# La correction vit maintenant dans `cumulative_by_platform`, en amont des deux, et
# c'est `test_the_levels_are_rebased_at_the_source` ci-dessus qui la garde. Le test
# retiré ne gardait pas une propriété perdue : il gardait un MÉCANISME qui n'existe
# plus, et un garde qui décrit une implémentation disparue passe au vert sur rien.
