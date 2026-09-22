"""Une période de SAISIE propose les fenêtres que sa source sait afficher.

Type: Test
Uses: src.dashboard.utils.entry_period (aucun Streamlit, aucune base)
Depends on: src/dashboard/views/saisie_s4a.py
Persists in: nothing

Demandé le 2026-09-22 : « début fin avec des valeurs à rentrer c'est pas très
agréable ». Deux paires de `st.date_input("Début") / ("Fin")` vivaient dans la page
de saisie S4A, sans le moindre raccourci.

Le fond dépasse le confort, et c'est ce que ce garde protège. Spotify for Artists
n'affiche un chiffre que pour **7 jours, 28 jours et 12 mois**. Une paire de dates
libres invite à saisir « du 3 au 19 » — une période pour laquelle la source ne
produit aucune valeur. Le champ accepte alors un nombre que rien ne peut avoir
produit, et la colonne `period_start` / `period_end` le garde pour toujours.

⚠️ **Ce garde ne prétend PAS unifier les périodes de l'app.** ADR-020 tranche
l'inverse, sur mesure : les deux vocabulaires existants (calendaire sur l'accueil,
ancré sur un évènement sur les pages plateforme) répondent à deux questions et les
unifier appauvrirait le second. Celui-ci en est un TROISIÈME, et assumé : lire une
fenêtre et déclarer la fenêtre qui a produit une valeur ne sont pas le même geste.

Ce qu'il couvre : les préréglages offerts, la résolution des bornes, le repli quand
la date de sortie est inconnue, et l'absence de `date_input` nu dans la page de
saisie. Ce qu'il NE couvre PAS : (1) les autres pages — `export_pdf`, `admin`,
`revenue_forecast` portent des `date_input`, et pour deux d'entre elles c'est une
DONNÉE métier (la date d'un coût), pas un filtre ; (2) que la valeur saisie
corresponde vraiment à la fenêtre choisie — aucun code ne peut le savoir ; (3) les
deux autres modules de période, gardés ailleurs.
"""
from __future__ import annotations

import ast
import datetime as _dt
from pathlib import Path

import pytest

from src.dashboard.utils.entry_period import DEFAULT, PRESETS, resolve

_ROOT = Path(__file__).resolve().parents[1]
_PAGE = _ROOT / "src" / "dashboard" / "views" / "saisie_s4a.py"
_TODAY = _dt.date(2026, 9, 22)


def test_the_windows_s4a_can_display_are_all_offered():
    """7 j, 28 j, 12 mois — les trois que la source sait rendre."""
    for cle in ("7d", "28d", "12m"):
        assert cle in PRESETS, (
            f"la fenêtre {cle} n'est plus offerte — c'est pourtant l'une des trois "
            "pour lesquelles Spotify for Artists affiche un chiffre à recopier"
        )


def test_the_default_is_the_window_the_model_reads():
    """28 jours : c'est la fenêtre qui alimente les labels d'entraînement."""
    assert DEFAULT == "28d"


@pytest.mark.parametrize("preset,jours", [("7d", 7), ("28d", 28), ("12m", 365)])
def test_a_preset_resolves_to_its_own_length(preset, jours):
    f = resolve(preset, _TODAY)
    assert f.days == jours and f.end == _TODAY
    assert f.preset == preset


def test_since_release_starts_at_the_release():
    sortie = _dt.date(2026, 9, 1)
    f = resolve("release", _TODAY, release=sortie)
    assert f.start == sortie and f.end == _TODAY and f.preset == "release"


def test_an_unknown_release_falls_back_and_SAYS_which_window_it_used():
    """Le repli ne DEVINE pas une date de sortie.

    Inventer une borne écrirait une période fausse dans une colonne que personne ne
    relira. Le repli déclare donc `28d` — et la page l'affiche à l'écran.
    """
    f = resolve("release", _TODAY, release=None)
    assert f.preset == "28d", (
        f"repli sur {f.preset!r} : une date de sortie inconnue ne doit pas produire "
        "une fenêtre qui se présente comme ancrée sur la sortie"
    )
    assert f.days == 28


def test_a_custom_range_is_used_verbatim():
    a, b = _dt.date(2026, 9, 3), _dt.date(2026, 9, 19)
    f = resolve("custom", _TODAY, custom=(a, b))
    assert (f.start, f.end, f.preset) == (a, b, "custom")


def test_custom_survives_because_a_release_has_no_s4a_window():
    """L'inverse du garde, et il compte autant.

    Retirer « sur mesure » au motif que S4A n'a que trois fenêtres supprimerait le
    cas des premiers jours d'une sortie, qu'on lit sur un graphique. Une règle qui
    ne vaut que par défaut ne doit pas devenir une interdiction.
    """
    assert "custom" in PRESETS


def _date_inputs_in(path: Path) -> list[int]:
    """Les `st.date_input` du fichier, par NUMÉRO DE LIGNE, lus à l'AST.

    À l'AST et pas au texte : un commentaire qui PARLE de `date_input` — et ce
    fichier en porte deux, qui expliquent précisément pourquoi ils ont disparu —
    ferait rougir un prédicat textuel sur du code correct. Ce dépôt a pris quatre
    gardes au vert sur leur propre commentaire en une soirée.
    """
    arbre = ast.parse(path.read_text(encoding="utf-8"))
    return [n.lineno for n in ast.walk(arbre)
            if isinstance(n, ast.Call)
            and getattr(n.func, "attr", "") == "date_input"]


def test_the_entry_page_has_no_bare_date_input_left():
    lignes = _date_inputs_in(_PAGE)
    assert not lignes, (
        f"`st.date_input` nu en ligne(s) {lignes} de saisie_s4a.py. Les fenêtres de "
        "saisie passent par `entry_period_selector` — sinon la page accepte une "
        "période pour laquelle Spotify for Artists n'affiche aucun chiffre."
    )


def test_the_detector_would_see_a_bare_date_input(tmp_path):
    """Le garde se prouve lui-même — sans ça, son zéro ne vaut rien."""
    faux = tmp_path / "vue.py"
    faux.write_text(
        "import streamlit as st\n"
        "# on parle de st.date_input dans un commentaire, ça ne doit rien déclencher\n"
        'def show():\n    st.date_input("Début")\n',
        encoding="utf-8")
    assert _date_inputs_in(faux) == [4], (
        "le détecteur ne voit pas un `date_input` réel, ou il compte le commentaire"
    )


def test_the_selector_is_reachable_from_the_page():
    """Présence ≠ atteignabilité : la page doit VRAIMENT l'importer."""
    arbre = ast.parse(_PAGE.read_text(encoding="utf-8"))
    importe = any(
        isinstance(n, ast.ImportFrom)
        and n.module == "src.dashboard.utils.entry_period"
        and any(a.name == "entry_period_selector" for a in n.names)
        for n in ast.walk(arbre))
    assert importe, "saisie_s4a.py n'importe pas `entry_period_selector`"
