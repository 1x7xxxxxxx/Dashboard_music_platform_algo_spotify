"""Une probabilité posée sur le plancher du sigmoïde ne classe rien.

Type: Test
Uses: src.utils.ml_inference._calibrate, machine_learning/models/v3/calibration.json
Depends on: rien d'autre — aucune base, aucun Streamlit
Persists in: nothing

⚠️ CE GARDE EXISTE POUR EMPÊCHER DE RECONSTRUIRE UN CLASSEMENT SUR DU BRUIT.

Mesuré en production le 2026-09-22, sur les dix titres de l'artiste 1 :

========  ==================  ====================  ==================
algo      plancher (brut=0)   production            score brut réel
========  ==================  ====================  ==================
DW        **6,53 %**          6,95 → 7,31 %         0,016 → 0,028
RR        **6,51 %**          6,54 → 6,56 %         **0,0013 → 0,0020**
RADIO     **10,72 %**         11,01 → 11,75 %       0,007 → 0,024
========  ==================  ====================  ==================

La calibration Platt (`ml_inference._calibrate`) applique
`sigmoid(coef · p_brut + intercept)`. Les trois intercepts étant négatifs, un score
brut NUL ne rend pas 0 % : il rend le **plancher** du sigmoïde. Et il faut un score
brut de **0,49 à 0,62** pour atteindre 50 % après calibration.

Conséquence, et c'est tout le sujet : quand `rr_probability` va de 0,0654 à 0,0656
sur dix titres, **le modèle n'hésite pas entre eux**. Le classifieur rend ~0,0015
pour tout le monde et Platt mappe ce presque-zéro sur 6,51 %. Les « 0,02 point
d'écart » sont l'image, comprimée par la sigmoïde, d'un écart de score brut de
**0,0007**.

Ce que le dépôt en a tiré
--------------------------
Le `Score /20` (`_loaders.py:_compute_score_20`) prenait ces fractions de point et
les **étirait en min-max sur une échelle de 20**. Il fabriquait l'apparence d'une
discrimination à partir d'une donnée qui n'en portait aucune — le nombre le plus
trompeur de la vue. Il est supprimé, et ce fichier est ce qui empêche d'en écrire
un deuxième.

⚠️ La probabilité n'est PAS fausse pour autant : la bande de calibration 0–20 %
annonce « réussite observée ~7 %, n=384 », ce qui est la bonne réponse. Elle est
vraie et **inutile pour comparer deux titres**. C'est pourquoi elle reste affichée
— en dernière colonne, marquée « ≈ plancher ».

Ce que ce garde NE couvre PAS
------------------------------
(1) Il ne juge pas la QUALITÉ du modèle — qu'un classifieur rende zéro sur ce
catalogue est un problème de données d'entraînement, hors de portée d'un test de
vue. (2) Il ne vérifie aucune surface d'affichage : qu'une figure trie par
probabilité lui est invisible. (3) Un autre algorithme, calibré autrement, ne serait
pas vu tant qu'il n'est pas dans `calibration.json`.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_CALIB = _ROOT / "machine_learning" / "models" / "v3" / "calibration.json"

# Les étendues mesurées en production le 2026-09-22 (artiste 1, dix titres).
# Elles ne sont pas la cible du garde — elles sont le CAS RÉEL sur lequel il
# raisonne, gardé pour que la démonstration reste rejouable.
_PROD_2026_09_22 = {
    "dw": (0.0695, 0.0731),
    "rr": (0.0654, 0.0656),
    "radio": (0.1101, 0.1175),
}


def _coeffs() -> dict:
    return json.loads(_CALIB.read_text(encoding="utf-8"))


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def _inverse(p: float, coef: float, intercept: float) -> float:
    """Le score brut qui produirait cette probabilité calibrée."""
    return (math.log(p / (1.0 - p)) - intercept) / coef


def test_the_calibration_file_is_where_the_code_looks_for_it():
    assert _CALIB.exists(), (
        f"{_CALIB} a disparu. Sans lui `_calibrate` est l'identité (repli documenté), "
        "et les probabilités affichées changent de sens sans que rien ne le dise."
    )


@pytest.mark.parametrize("algo", ["dw", "rr", "radio"])
def test_a_zero_raw_score_does_not_render_zero_percent(algo):
    """Le fait central : score brut nul ⇒ plancher, pas zéro."""
    c = _coeffs()[algo]
    plancher = _sigmoid(c["intercept"])
    assert plancher > 0.05, (
        f"{algo} : le plancher vaut {plancher:.4f}. S'il tombe sous 5 %, la "
        "démonstration de ce fichier ne tient plus — relire la calibration."
    )
    assert plancher < 0.20, (
        f"{algo} : plancher à {plancher:.4f}, au-dessus de la bande 0-20 %."
    )


@pytest.mark.parametrize("algo", ["dw", "rr", "radio"])
def test_the_production_spread_is_a_raw_score_of_almost_nothing(algo):
    """LA raison d'être du fichier, et l'assertion qui décide.

    Sur la plage observée en production, l'écart de score BRUT entre le meilleur et
    le pire titre doit rester sous 0,03 — c'est-à-dire un vingtième de ce qu'il
    faudrait pour changer de bande de décision.
    """
    c = _coeffs()[algo]
    bas, haut = _PROD_2026_09_22[algo]
    brut_bas = _inverse(bas, c["coef"], c["intercept"])
    brut_haut = _inverse(haut, c["coef"], c["intercept"])
    ecart_brut = brut_haut - brut_bas
    assert ecart_brut < 0.03, (
        f"{algo} : l'écart de score brut vaut {ecart_brut:.4f} sur la plage de "
        f"production ({bas:.4f} → {haut:.4f}). Au-dessus de 0,03, un classement par "
        "probabilité commencerait à porter de l'information — ce fichier devrait "
        "alors être relu, pas contourné."
    )


@pytest.mark.parametrize("algo", ["dw", "rr", "radio"])
def test_reaching_a_decision_band_needs_a_raw_score_nothing_here_has(algo):
    """Il faut un score brut de ~0,5 pour atteindre 50 % calibré.

    Sans ce test, « les titres sont sur le plancher » resterait une affirmation sur
    un cas ; avec lui, on borne ce qu'il FAUDRAIT pour en sortir.
    """
    c = _coeffs()[algo]
    requis = _inverse(0.50, c["coef"], c["intercept"])
    _, haut = _PROD_2026_09_22[algo]
    observe = _inverse(haut, c["coef"], c["intercept"])
    assert requis > 0.40, f"{algo} : 50 % atteint dès un brut de {requis:.3f}"
    assert observe < requis / 10, (
        f"{algo} : le meilleur titre observé est à {observe:.4f} de score brut, il "
        f"en faudrait {requis:.3f} — soit {requis / max(observe, 1e-9):.0f}× plus."
    )


def test_the_floor_is_what_the_running_code_computes(monkeypatch):
    """Le garde interroge `_calibrate` lui-même, pas une formule recopiée.

    Une constante recopiée diverge le jour où `_calibrate` change de forme. C'est le
    motif que ce dépôt appelle `a-second-door-that-knows-fewer-sources-than-the-first`.
    """
    from src.utils import ml_inference

    for algo in ("dw", "rr", "radio"):
        c = _coeffs()[algo]
        attendu = _sigmoid(c["intercept"])
        obtenu = ml_inference._calibrate(algo, 0.0)
        assert obtenu == pytest.approx(attendu, abs=1e-9), (
            f"{algo} : `_calibrate(0.0)` rend {obtenu}, la sigmoïde de l'intercept "
            f"rend {attendu}. Les deux ont divergé."
        )


def test_the_guard_would_see_a_calibration_that_stopped_calibrating():
    """Anti-vacuité — muter la calibration à l'identité DOIT casser la démonstration.

    Avec `coef=1, intercept=0`, le plancher tombe à 50 % et l'écart brut devient
    l'écart calibré. Les deux assertions centrales du fichier doivent alors être
    fausses ; si elles survivent, elles ne mesurent rien.
    """
    identite = {"coef": 1.0, "intercept": 0.0}
    plancher = _sigmoid(identite["intercept"])
    assert plancher == pytest.approx(0.5), "la mutation ne produit pas le cas attendu"

    # (a) le plancher : `test_a_zero_raw_score_does_not_render_zero_percent` exige
    #     plancher < 0,20 — sous identité il vaut 0,5, l'assertion tombe.
    assert not (plancher < 0.20), (
        "sous calibration identité le plancher vaut 0,5 : l'assertion du plancher "
        "doit tomber, sinon elle est vacante"
    )

    # (b) l'écart brut. ⚠️ MA PREMIÈRE NOTE ICI ÉTAIT FAUSSE, et la mutation l'a
    #     montrée : j'avais écrit que sous identité « l'écart calibré EST l'écart
    #     brut » et resterait donc sous 0,03. C'est faux — l'inverse d'une sigmoïde
    #     d'identité est le LOGIT, pas l'identité. Mesuré : DW 0,0544, RADIO 0,0734,
    #     tous deux au-dessus de 0,03. Seul RR (0,0033) survivrait.
    #     Les deux assertions mordent donc, et pas pour la raison que j'avais écrite.
    bas, haut = _PROD_2026_09_22["dw"]
    logit = lambda p: math.log(p / (1.0 - p))            # noqa: E731 — local, une ligne
    assert (logit(haut) - logit(bas)) > 0.03, (
        "sous identité, l'écart de score brut de DW doit dépasser le seuil de 0,03 — "
        "sinon l'assertion d'écart serait vacante sur ce mutant"
    )
