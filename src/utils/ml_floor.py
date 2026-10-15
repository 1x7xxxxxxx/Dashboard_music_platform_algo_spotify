"""The ML calibration floor — the ONE door between a probability and a display.

Type: Utility
Uses: src.utils.ml_inference (calibration coefficients)
Depends on: nothing under src/dashboard
Persists in: nothing

Moved from `src/dashboard/utils/algo_preview_data.py` (R626, arc 2): the weekly digest
(`src/utils/digest_queries.py`) needs the same refusal as every dashboard surface, and
reading it from the dashboard was an upward arc. `algo_preview_data` re-imports the three
names, so its callers are unchanged.
"""
from __future__ import annotations

import math


#: Le score BRUT en dessous duquel on considère que le modèle n'a rien tranché.
#:
#: Le seuil vit dans l'espace brut et non dans l'espace calibré, parce que c'est là
#: que le sens est. Il faut un score brut de **0,49 à 0,62** pour atteindre 50 %
#: après calibration ; 0,05 en est le douzième. En production le 2026-09-22, les dix
#: titres de l'artiste 1 sont entre **0,0013 et 0,028** — tous largement dessous.
BRUT_NEGLIGEABLE = 0.05


def sur_le_plancher(algo: str, proba) -> bool:
    """Cette probabilité traduit-elle un score brut négligeable ?

    A bare predicate: no surface calls it directly any more — they go through
    `proba_affichable` here and `format_proba` (algo_preview_data), which REFUSE a floor value instead of
    presenting it as a measure that distinguishes this title from the others.

    ⚠️ L'inversion passe par les coefficients que `ml_inference._calibrate` UTILISE,
    jamais par une copie. Une constante recopiée diverge le jour où le modèle est
    réentraîné, et le dépôt appelle ça
    `a-second-door-that-knows-fewer-sources-than-the-first`.
    """
    if proba is None:
        return False
    try:
        p = float(proba)
    except (TypeError, ValueError):
        return False
    if not 0.0 < p < 1.0:
        return False
    try:
        from src.utils.ml_inference import _load_json

        c = (_load_json("calibration.json") or {}).get(algo.lower())
    except Exception:                                    # noqa: BLE001
        return False
    if not c or not c.get("coef"):
        return False
    brut = (math.log(p / (1.0 - p)) - c["intercept"]) / c["coef"]
    return brut <= BRUT_NEGLIGEABLE


def proba_affichable(algo: str, proba) -> float | None:
    """THE single door between an ML probability and a display or a decision.

    Returns the probability as a float in [0, 1] when it is a measure that
    distinguishes this title, and `None` when it is absent, unreadable, or on the
    calibration floor (`sur_le_plancher`). The policy is REFUSE, never mark: a floor
    value is the model saying nothing, so no surface prints it, compares it, ranks on
    it or draws a threshold verdict from it. Before this door, the preview refused,
    the catalogue marked « ≈ plancher », and eleven other surfaces printed the floor
    as a distinguishing percentage (class `two-surfaces-two-truths`, 2026-09-26).
    """
    if proba is None:
        return None
    try:
        p = float(proba)
    except (TypeError, ValueError):
        return None
    if p != p:                                            # NaN
        return None
    if sur_le_plancher(algo, p):
        return None
    return p
