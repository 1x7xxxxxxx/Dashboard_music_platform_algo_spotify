"""The KPI dossier reads in the owner's order, and a fiche to correct says WHAT (R286).

Owner, 2026-09-28: « une hiérarchie : à corriger, ensuite à fusionner, ensuite à garder,
ensuite validé » and « tu me dis corriger, mais corriger quoi ? ».

Does not cover: the HTML layout itself — the PDF is regenerated and looked at.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "dev" / "charts_dossier"))

import main as dossier  # noqa: E402


def test_the_sections_come_in_the_owners_order():
    order = [k for k, _ in dossier.ORDER]
    assert order.index("corriger") < order.index("fusionner") < order.index("garder") \
        < order.index("valide")
    assert order[-1] == "valide"


def test_the_owners_verdict_places_the_fiche_before_mine():
    assert dossier.place({"v": "garder", "owner_v": "corriger"}, "a-faire") == "corriger"
    assert dossier.place({"v": "corriger"}, "sans-avis") == "corriger"
    assert dossier.place({"v": "garder", "owner_v": "valider"}, "a-faire") == "valide"
    assert dossier.place({"v": "corriger"}, "valide") == "valide"


def test_a_fiche_to_correct_says_what():
    entry = {"actions": [{"qui": "moi", "texte": "Lire par une vue or", "rid": "R289"}]}
    assert "Lire par une vue or" in dossier.what_to_do({"v": "corriger"}, entry)
    bare = dossier.what_to_do({"v": "fusionner", "note": "Deux figures pour une question"}, None)
    assert "Deux figures pour une question" in bare and "pas encore d'action" in bare
    assert dossier.what_to_do({"v": "garder"}, entry) == ""
