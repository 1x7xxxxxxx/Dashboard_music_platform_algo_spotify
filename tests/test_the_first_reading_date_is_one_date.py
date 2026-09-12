"""« Depuis quand mesure-t-on cette plateforme ? » n'a qu'une réponse.

Type: Test
Uses: pytest, platform_absence._late_starts
Depends on: src/dashboard/utils/platform_absence.py, src/dashboard/utils/platform_chart.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Mesuré en production le 2026-09-13, artiste 1 — la même figure, deux réglages :

    SoundCloud, pas JOUR, « par période » → « mesurée depuis le 31/03/2026 »
    SoundCloud, pas MOIS                  → « mesurée depuis décembre 2025 »

**Trois mois et demi d'écart pour le même fait.** La cause est que `aligned` change de
NATURE selon le mode : série quotidienne en « par période » au pas du jour, niveaux
partout ailleurs. Or la série quotidienne d'un compteur est une DIFFÉRENCE entre deux
relevés CONSÉCUTIFS — elle ne peut pas commencer avant le deuxième jour où deux relevés
se suivent. Pour SoundCloud, relevée le 16/12/2025 puis de façon espacée, cela n'est
arrivé qu'en mars.

La vraie date est celle du premier RELEVÉ, qui vit dans les niveaux (la couche or).
C'est la même famille que tout ce qui a été corrigé cette semaine : une question, une
source, une réponse.

⚠️ Ce fait-là compte plus qu'un détail d'affichage. C'est la phrase qui explique
pourquoi la courbe cumulée part d'une falaise — « j'ai fait des streams avant le 1er
novembre 2025 […] ça me les marque en cumulé de 0 à des dizaines de milliers
directement ». Si elle donne la mauvaise date, elle envoie chercher la panne au mauvais
endroit.

Mutations vues rouges avant écriture (2026-09-13) :
  * `levels=cumulative` retiré de l'appel dans `platform_chart` →
    test_the_date_comes_from_the_readings_not_the_deltas ÉCHOUE ;
  * `_late_starts` ignorant `levels` quand il est fourni → même test ÉCHOUE.
"""
from __future__ import annotations

import ast
import datetime as _d
from pathlib import Path

from src.dashboard.utils.platform_absence import _late_starts

_CHART = Path(__file__).resolve().parents[1] / "src/dashboard/utils/platform_chart.py"

_SPAN = [_d.date(2025, 1, 1) + _d.timedelta(days=i) for i in range(400)]
_LABELS = {"soundcloud": "☁️ SoundCloud"}

# LA MISE EN SCÈNE EST CELLE DE LA PRODUCTION. Le compteur est relevé dès le 100ᵉ jour,
# mais deux relevés ne se SUIVENT qu'à partir du 300ᵉ — donc la série quotidienne, qui
# est une différence, ne commence qu'à ce moment-là.
_FIRST_READING = _SPAN[100]
_LEVELS = {"soundcloud": ([(_SPAN[i], 1000 + i) for i in range(100, 300, 9)]
                          + [(_SPAN[i], 1200 + i) for i in range(300, 400)])}
# `aligned` tel que le mode « par période » au pas du jour le fabrique : des `None`
# jusqu'au premier écart entre deux jours consécutifs.
_ALIGNED_DAILY = {"soundcloud": [None] * 300 + [1] * 100}
# `aligned` tel que le mode cumulé le fabrique : les niveaux reportés en avant.
_ALIGNED_LEVELS = {"soundcloud": [None] * 100 + [1000] * 300}


def test_the_date_comes_from_the_readings_not_the_deltas():
    """Les deux formes d'`aligned` doivent rendre la MÊME date."""
    daily = _late_starts(_ALIGNED_DAILY, ["soundcloud"], _SPAN, _LABELS,
                         levels=_LEVELS)
    levels = _late_starts(_ALIGNED_LEVELS, ["soundcloud"], _SPAN, _LABELS,
                          levels=_LEVELS)
    assert daily == levels, (
        f"la date de première mesure change avec le mode : {daily} en « par période » "
        f"au pas du jour, {levels} en cumulé. C'est le défaut mesuré en production le "
        "2026-09-13 — SoundCloud disait 31/03/2026 d'un côté et décembre 2025 de "
        "l'autre, trois mois et demi d'écart pour le même fait.")
    assert daily and daily[0][1] == _FIRST_READING, (
        f"la date rendue est {daily[0][1] if daily else None} au lieu du premier "
        f"RELEVÉ ({_FIRST_READING}). La série quotidienne d'un compteur est une "
        "différence entre deux relevés consécutifs : elle commence forcément après.")


def test_without_levels_the_aligned_series_still_answers():
    """Non-vacuité : une source vraiment quotidienne (Spotify) n'a pas de niveaux."""
    got = _late_starts(_ALIGNED_DAILY, ["soundcloud"], _SPAN, _LABELS, levels=None)
    assert got and got[0][1] == _SPAN[300], (
        f"sans niveaux, la date doit venir d'`aligned` : attendu {_SPAN[300]}, "
        f"obtenu {got[0][1] if got else None}. Sans ce repli, une plateforme sans "
        "couche or perdrait sa mention de préhistoire.")


def test_a_platform_measured_from_the_first_step_says_nothing():
    """Pas de préhistoire à expliquer — le dire serait du bruit."""
    levels = {"soundcloud": [(_SPAN[0], 10), (_SPAN[50], 20)]}
    aligned = {"soundcloud": [1] * 400}
    assert not _late_starts(aligned, ["soundcloud"], _SPAN, _LABELS, levels=levels), (
        "une plateforme mesurée dès le premier pas de la fenêtre porte une mention "
        "de préhistoire : c'est du bruit sur la ligne la plus utile de la figure.")


def test_the_chart_passes_its_levels():
    """Une source de vérité qu'on ne transmet pas ne sert à rien."""
    fn = next(n for n in ast.walk(ast.parse(_CHART.read_text(encoding="utf-8")))
              if isinstance(n, ast.FunctionDef) and n.name == "render_platform_chart")
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "_late_starts"]
    assert calls, "`render_platform_chart` n'appelle plus `_late_starts`"
    for call in calls:
        assert any(kw.arg == "levels" for kw in call.keywords), (
            "`_late_starts` est appelé SANS `levels` : il retombe sur `aligned`, dont "
            "la nature change avec le mode, et la date redevient double.")
