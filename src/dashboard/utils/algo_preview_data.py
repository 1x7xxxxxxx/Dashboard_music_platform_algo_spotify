"""The shared computations of Road to Algo — one definition, read by the Premium page AND the
free preview.

Type: Utility
Uses: src.utils.ml_inference (calibration), v_meta_daily, v_s4a_song_daily, ml_song_predictions
Depends on: nothing from views/
Persists in: nothing

R193 (2026-09-26). The free « Aperçu : déclencher les algos » page needs the same floor test,
budget and prediction loader as the Premium `trigger_algo` package. They lived there as private
helpers; moved HERE so both read one definition (a copy would drift — the class
`a-second-door-that-knows-fewer-sources-than-the-first`). The old modules re-export them under
their old names, so every existing caller and test keeps working unchanged.
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
    `proba_affichable` / `format_proba` below, which REFUSE a floor value instead of
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


#: What every surface writes INSTEAD of a floor probability. One wording, one policy.
PLANCHER_TEXTE = "pas d'estimation fiable"


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


def texte_plancher() -> str:
    """`PLANCHER_TEXTE` in the viewer's language (key `common.ml_floor`)."""
    try:
        from src.dashboard.utils.i18n import t

        return t("common.ml_floor", PLANCHER_TEXTE)
    except Exception:                                    # noqa: BLE001 — headless caller
        return PLANCHER_TEXTE


def format_proba(algo: str, proba, decimals: int = 0, absent: str = "—",
                 floor_text: str | None = None) -> str:
    """The text of an ML probability: `'60%'`, the floor text, or `absent`.

    `floor_text` lets a surface with its own language channel (the PDF's `_t`, a
    mail) pass its translation; by default the viewer's `t()` is used.
    """
    p = proba_affichable(algo, proba)
    if p is not None:
        return f"{p * 100:.{decimals}f}%"
    try:
        present = proba is not None and float(proba) == float(proba)
    except (TypeError, ValueError):
        present = False
    if not present:
        return absent
    return floor_text if floor_text is not None else texte_plancher()


def budget_pour_streams(streams_manquants: float, cout_par_stream: float | None) -> float | None:
    """Ce que coûterait d'acheter ces écoutes, au coût observé — ou `None`.

    ⚠️ **Ce nombre porte une limite qu'il faut afficher AVEC lui.** `cout_par_stream`
    est agrégé sur toutes les campagnes et tous les titres de l'artiste : il ne dit
    pas ce que coûtent les écoutes de CE titre. L'attribution passerait par
    `campaign_track_mapping`, qui porte 19 correspondances, et la dépense Meta
    s'arrête au 2024-09-30 quand les écoutes vont jusqu'en 2026.

    On le rend quand même, parce qu'un ordre de grandeur aide à décider d'un budget
    — mais la vue doit écrire que c'en est un, et non un devis.
    """
    if not cout_par_stream or cout_par_stream <= 0 or streams_manquants is None:
        return None
    manque = float(streams_manquants)
    return manque * float(cout_par_stream) if manque > 0 else 0.0


def cout_par_stream(db, artist_id, date_from, date_to) -> float | None:
    """Dépense ÷ écoutes sur la fenêtre — agrégé TOUS TITRES, et la vue le dit.

    Extrait pour que le panneau de réglages lise la même valeur que les tuiles de
    budget plus bas. Deux calculs du même coût finiraient par diverger.
    """
    try:
        dep = db.fetch_query(
            "SELECT COALESCE(SUM(spend), 0) FROM v_meta_daily "
            "WHERE artist_id = %s AND day BETWEEN %s AND %s",
            (artist_id, date_from, date_to)) if artist_id else None
        st_ = db.fetch_query(
            "SELECT COALESCE(SUM(streams), 0) FROM v_s4a_song_daily "
            "WHERE artist_id = %s AND day BETWEEN %s AND %s",
            (artist_id, date_from, date_to)) if artist_id else None
    except Exception:                                    # noqa: BLE001
        return None
    if not dep or not st_:
        return None
    depense, streams = float(dep[0][0] or 0), float(st_[0][0] or 0)
    return depense / streams if depense > 0 and streams > 0 else None


def load_ml_pred(db, track: str, artist_id) -> dict | None:
    try:
        if artist_id:
            rows = db.fetch_query(
                """SELECT dw_probability, rr_probability, radio_probability,
                          dw_streams_forecast_7d, rr_streams_forecast_7d,
                          radio_streams_forecast_7d, pi_forecast_7d,
                          prediction_date, model_version, features_json
                   FROM ml_song_predictions
                   WHERE artist_id = %s AND song = %s
                   ORDER BY prediction_date DESC LIMIT 1""",
                (artist_id, track)
            )
        else:
            rows = db.fetch_query(
                """SELECT dw_probability, rr_probability, radio_probability,
                          dw_streams_forecast_7d, rr_streams_forecast_7d,
                          radio_streams_forecast_7d, pi_forecast_7d,
                          prediction_date, model_version, features_json
                   FROM ml_song_predictions
                   WHERE song = %s
                   ORDER BY prediction_date DESC LIMIT 1""",
                (track,)
            )
        if rows:
            r = rows[0]
            return {
                "dw_probability": r[0], "rr_probability": r[1], "radio_probability": r[2],
                "dw_streams_forecast_7d": r[3], "rr_streams_forecast_7d": r[4],
                "radio_streams_forecast_7d": r[5], "pi_forecast_7d": r[6],
                "prediction_date": r[7], "model_version": r[8], "features_json": r[9],
            }
    except Exception:
        pass
    return None
