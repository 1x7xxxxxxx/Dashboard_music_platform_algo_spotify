"""Le pas d'une figure ne dépend pas de la PAGE qui la dessine.

Type: Test
Uses: ast
Depends on: src/dashboard/utils/platform_chart, src/dashboard/views/home.py,
            src/dashboard/utils/pdf_charts.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Deux échelles décidaient du pas jour/semaine/mois, et elles divergeaient au-delà de
92 jours. Mesuré le 2026-09-20 (R140 §16.12) :

    fenêtre  120 j : accueil -> day    | figure partagée -> week
    fenêtre  365 j : accueil -> month  | figure partagée -> week
    fenêtre 1356 j : accueil -> month  | figure partagée -> week

`home.py` portait `_DAY_UNTIL_YEAR = 360` et `_MAX_BUCKETS = 60` (jour → mois → année,
**jamais semaine**) pendant que `platform_chart:608` et `pdf_charts:309` partageaient
`_WEEKLY_ABOVE_DAYS = 92`. **Même locataire, même figure, même jour** : le pas dépendait
de la page — l'accueil en mois, le PDF en semaine.

⚠️ **Et le cadrage de la roadmap était partiellement faux.** Elle annonçait « quatre
nombres — 360/60, 92, 90, 120 ». Vérifié : `120` désigne une troncature de chaîne et un
numéro de migration, sans rapport ; `90` est le préréglage du SÉLECTEUR de période
(`period_filter._default_preset`), qui répond à « quelle période pré-sélectionner », pas
à « à quel pas agréger ». Les nombres réellement en cause sont **360/60 contre 92**.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.dashboard.utils.platform_chart import (  # noqa: E402
    _MAX_BUCKETS, _WEEKLY_ABOVE_DAYS, default_step,
)


@pytest.mark.parametrize("jours,attendu", [
    (1, "day"), (60, "day"), (91, "day"),
    (92, "week"), (120, "week"), (365, "week"), (420, "week"),
    (1356, "month"),
    (2000, "year"),
    (None, "day"),
])
def test_the_ladder_is_monotone_and_measured(jours, attendu: str) -> None:
    """Les deux frontières viennent d'une mesure, pas d'un arrondi.

    92 jours : la COUVERTURE (SoundCloud 56 % de jours mesurés, YouTube 39 % — au pas
    quotidien, une bande empilée perdait des plateformes entières).
    60 seaux : la LISIBILITÉ.
    """
    assert default_step(jours) == attendu


def test_the_ladder_never_goes_backwards() -> None:
    """Un pas plus fin sur une fenêtre plus large serait une échelle cassée."""
    ordre = {"day": 0, "week": 1, "month": 2, "year": 3}
    precedent = -1
    for j in range(1, 2500, 7):
        rang = ordre[default_step(j)]
        assert rang >= precedent, (
            f"à {j} jours le pas redevient plus fin ({default_step(j)}) — l'échelle "
            "n'est pas monotone, donc élargir la fenêtre peut rendre la figure plus "
            "dense au lieu de plus lisible.")
        precedent = rang


def test_home_no_longer_carries_its_own_ladder() -> None:
    """LE GARDE. Lu à l'AST : un commentaire qui raconte l'ancienne échelle la nomme.

    `_DAY_UNTIL_YEAR` peut rester DÉFINI (d'autres lectures possibles) ; ce qui est
    interdit est qu'il serve encore à choisir un pas.
    """
    arbre = ast.parse((ROOT / "src/dashboard/views/home.py").read_text(encoding="utf-8"))
    assignations_de_pas = [
        n for n in ast.walk(arbre)
        if isinstance(n, ast.Assign)
        and any(getattr(t, "id", "") == "step" for t in n.targets)
        and isinstance(n.value, ast.Constant)]
    assert not assignations_de_pas, (
        f"`home.py` affecte encore `step` à une constante (l."
        f"{[n.lineno for n in assignations_de_pas]}) — il a donc sa propre échelle, et "
        "elle divergera de celle du PDF comme elle l'a fait jusqu'au 2026-09-20.")
    appelle = any(isinstance(n, ast.ImportFrom)
                  and any(a.name == "default_step" for a in n.names)
                  for n in ast.walk(arbre))
    assert appelle, "`home.py` n'importe pas `default_step` — il ne lit plus l'échelle."


def test_the_pdf_and_the_chart_read_the_same_boundary() -> None:
    """ANTI-VACUITÉ : si les deux surfaces cessaient de partager, l'unification serait vide."""
    for rel in ("src/dashboard/utils/pdf_charts.py",
                "src/dashboard/utils/platform_chart.py"):
        texte = (ROOT / rel).read_text(encoding="utf-8")
        assert "_WEEKLY_ABOVE_DAYS" in texte, (
            f"{rel} ne lit plus la frontière partagée — il en a donc une à lui.")
    assert _WEEKLY_ABOVE_DAYS == 92 and _MAX_BUCKETS == 60, (
        f"les frontières ont bougé ({_WEEKLY_ABOVE_DAYS}, {_MAX_BUCKETS}) sans que ce "
        "test le sache. Les deux sont MESURÉES — les changer demande une nouvelle mesure, "
        "pas un ajustement.")
