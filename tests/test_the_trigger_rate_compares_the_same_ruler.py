"""Le taux de trigger d'UN titre, au début et aujourd'hui — sans mentir sur l'écart.

R55, tranché le 2026-08-26 : **le taux de trigger est le % de chance d'intégrer
l'algorithme en question, et il porte sur UN SEUL titre.** Les trois candidates
proposées avant cette précision (part de catalogue, portes par titre, délai médian)
étaient toutes des agrégats de PORTEFEUILLE — la mauvaise grandeur.

Ce fichier garde les trois façons dont la section peut afficher une phrase fausse et
parfaitement lisible :

  * comparer une probabilité v1 à une v3 — l'écart mêle alors le titre et le modèle ;
  * rendre une absence comme un 0 % (défaut corrigé le 2026-08-24 sur `pi_gate`) ;
  * résumer une fenêtre de 30 jours par un point bruité, sans dire son effectif.
"""
from __future__ import annotations

import datetime as dt

import pytest

from src.utils.trigger_rate_history import (
    EARLY_DAYS, as_points, trigger_rate_then_and_now,
)

_D = dt.date(2026, 1, 1)


class _DB:
    """Rend des lignes dans l'ordre de colonnes exact de la requête."""

    def __init__(self, rows=None, boom=False):
        self._rows, self._boom = rows or [], boom

    def fetch_query(self, sql, params=None):
        if self._boom:
            raise RuntimeError("connection lost")
        return self._rows


def _row(day, dsr, ver, dw, rr, radio):
    return (_D + dt.timedelta(days=day), dsr, ver, dw, rr, radio)


def test_a_track_with_no_prediction_is_absent_not_zero():
    out = trigger_rate_then_and_now(_DB([]), 1, "Titre")
    assert out["early"] is None and out["now"] is None
    assert "aucune prédiction" in out["reason"]
    assert all(p["early"] is None and p["now"] is None for p in as_points(out))


def test_a_track_released_before_scoring_says_so():
    """Des prédictions existent, mais aucune dans les 30 premiers jours."""
    out = trigger_rate_then_and_now(
        _DB([_row(0, 200, "v3", 0.4, 0.3, 0.2)]), 1, "Titre")
    assert out["early"] is None
    assert out["now"] is not None, "l'état actuel reste lisible"
    assert str(EARLY_DAYS) in out["reason"] and "avant la mise en service" in out["reason"]
    assert all(p["delta"] is None for p in as_points(out))


def test_the_comparison_works_on_one_ruler():
    out = trigger_rate_then_and_now(_DB([
        _row(0, 5, "v3", 0.20, 0.10, 0.05),
        _row(1, 20, "v3", 0.30, 0.20, 0.15),
        _row(2, 300, "v3", 0.50, 0.40, 0.35),
    ]), 1, "Titre")
    assert out["comparable"] is True and out["reason"] is None
    assert out["early"]["n"] == 2
    # Médiane des deux points initiaux, pas le dernier ni le premier.
    assert out["early"]["dw_probability"] == pytest.approx(0.25)
    dw = next(p for p in as_points(out) if p["gate"] == "Discover Weekly")
    assert dw["now"] == pytest.approx(0.50)
    assert dw["delta"] == pytest.approx(0.25)


def test_two_model_versions_are_never_subtracted():
    """LE piège : v3 a été reconstruite en group-CV avec calibration OOF. Un écart
    entre v1 et v3 est en partie le modèle, pas le titre."""
    out = trigger_rate_then_and_now(_DB([
        _row(0, 10, "v1", 0.20, 0.10, 0.05),
        _row(2, 300, "v3", 0.60, 0.50, 0.40),
    ]), 1, "Titre")
    assert out["comparable"] is False
    assert "v1" in out["reason"] and "v3" in out["reason"]
    assert out["early"] is not None and out["now"] is not None, (
        "les deux valeurs restent affichables — c'est l'ÉCART qui ne l'est pas")
    assert all(p["delta"] is None for p in as_points(out)), (
        "un delta calculé entre deux règles différentes se lit comme une évolution")


def test_a_gate_the_model_did_not_predict_stays_absent():
    """`None` n'est pas 0.0 : une porte non prédite n'a pas une chance nulle."""
    out = trigger_rate_then_and_now(_DB([
        _row(0, 10, "v3", 0.2, None, None),
        _row(2, 300, "v3", 0.5, None, None),
    ]), 1, "Titre")
    rr = next(p for p in as_points(out) if p["gate"] == "Release Radar")
    assert rr["early"] is None and rr["now"] is None and rr["delta"] is None


def test_the_early_window_carries_its_count():
    """Une valeur sans effectif se lit comme une certitude — la leçon de `pi_gate`,
    où 66,7 % sur n=3 s'affichait aussi net que 99,4 % sur n=172."""
    out = trigger_rate_then_and_now(_DB([
        _row(0, 3, "v3", 0.1, 0.1, 0.1),
        _row(1, 9, "v3", 0.9, 0.9, 0.9),
        _row(2, 400, "v3", 0.5, 0.5, 0.5),
    ]), 1, "Titre")
    assert out["early"]["n"] == 2
    assert out["early"]["as_of"] is not None


def test_an_unreadable_history_is_named_never_silently_empty():
    """Une lecture qui échoue ne se déguise pas en « rien à lire » (règle du dépôt)."""
    out = trigger_rate_then_and_now(_DB(boom=True), 1, "Titre")
    assert out["early"] is None
    assert "illisible" in out["reason"]
    assert "RuntimeError" in out["reason"]


# ── le câblage : la section doit ATTEINDRE le PDF ────────────────────────────

@pytest.fixture(autouse=True)
def _render_in_french():
    """La langue du PDF est un état GLOBAL (`_set_lang`), donc héritée du test
    précédent. Les assertions ci-dessous portent sur des libellés : elles doivent
    choisir leur langue au lieu de subir celle de l'ambiance — sinon elles passent ou
    échouent selon l'ordre d'exécution, ce qui est pire qu'un échec franc.
    """
    from src.dashboard.utils.pdf_exporter._config import _set_lang

    _set_lang("fr")
    yield
    _set_lang("fr")


def _renderer():
    from src.dashboard.utils.pdf_exporter._renderers import _render_trigger_then_now
    return _render_trigger_then_now


def test_the_section_is_actually_rendered_into_the_report():
    """« Correct et jamais atteint » est la classe la plus fréquente de ce dépôt.

    Asserté sur l'AST : le renderer doit être APPELÉ dans la composition du HTML, et
    la collecte doit remplir la clé qu'il lit.
    """
    import ast
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1]
           / "src/dashboard/utils/pdf_exporter/_report.py").read_text(encoding="utf-8")
    called = {n.func.id for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "_render_trigger_then_now" in called, (
        "la section R55 est écrite et jamais appelée — elle n'existe pas pour l'artiste")
    assert "trigger_rate_then_and_now" in called, "la collecte n'est pas branchée"
    assert "'trigger_then_now': trigger_then_now," in src


def test_the_section_only_exists_on_a_single_track_report():
    """La grandeur porte sur UN titre. Sur un rapport multi-titres, `_focus_song`
    retomberait sur la dernière sortie et afficherait l'évolution d'un AUTRE titre."""
    import pathlib

    import ast

    src = (pathlib.Path(__file__).resolve().parents[1]
           / "src/dashboard/utils/pdf_exporter/_report.py").read_text(encoding="utf-8")

    # L'AST, pas un découpage de texte : la première version coupait sur une ligne
    # vide et avalait des lignes voisines qui nomment `_focus_song` pour une tout
    # autre raison — un faux positif dans le garde, donc un garde qu'on désactive.
    found = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.If):
            continue
        if ast.unparse(node.test).strip() != "_single_song":
            continue
        body = ast.unparse(node.body)
        if "trigger_rate_then_and_now" in body:
            found.append(body)
    assert found, (
        "la collecte R55 n'est pas sous `if _single_song:` — sur un rapport "
        "multi-titres elle parlerait d'un AUTRE titre que celui demandé")
    assert all("_focus_song" not in b for b in found), (
        "la section retombe sur la dernière sortie")


def test_an_absent_measure_is_never_drawn_as_zero_percent():
    html = _renderer()({"song": "T", "early": None, "comparable": False,
                        "now": {"n": 1, "as_of": _D, "model_version": "v3",
                                "dw_probability": 0.4, "rr_probability": None,
                                "radio_probability": None},
                        "reason": "aucune mesure dans les 30 premiers jours"})
    # `"0%" not in html` serait faux sur « 40% » — le garde doit lire les CELLULES,
    # pas la chaîne entière. Première version de cette assertion : un faux positif.
    import re

    cells = re.findall(r"<td>([^<]*)</td>", html) + re.findall(r"<b>([^<]*)</b>", html)
    assert "0%" not in cells, (
        f"une absence dessinée en 0 % dit l'inverse de « on ne sait pas » : {cells}")
    assert "non mesuré" in cells
    assert "40%" in cells
    assert "aucune mesure" in html


def test_a_cross_version_comparison_shows_both_values_and_no_delta():
    html = _renderer()({
        "song": "T", "comparable": False,
        "reason": "modèles différents (v1 → v3)",
        "early": {"n": 2, "as_of": _D, "model_version": "v1",
                  "dw_probability": 0.2, "rr_probability": 0.1, "radio_probability": 0.1},
        "now": {"n": 1, "as_of": _D, "model_version": "v3",
                "dw_probability": 0.6, "rr_probability": 0.5, "radio_probability": 0.4},
    })
    assert "20%" in html and "60%" in html, "les deux valeurs restent lisibles"
    assert "pts" not in html, "aucun écart ne doit être affiché entre deux règles"
    assert "modèles différents" in html


def test_a_real_comparison_shows_its_delta_and_its_count():
    html = _renderer()({
        "song": "T", "comparable": True, "reason": None,
        "early": {"n": 4, "as_of": _D, "model_version": "v3",
                  "dw_probability": 0.20, "rr_probability": None, "radio_probability": 0.10},
        "now": {"n": 1, "as_of": _D, "model_version": "v3",
                "dw_probability": 0.50, "rr_probability": None, "radio_probability": 0.05},
    })
    assert "▲ 30 pts" in html and "▼ 5 pts" in html
    assert "4" in html, "l'effectif de la fenêtre initiale doit voyager avec la valeur"
