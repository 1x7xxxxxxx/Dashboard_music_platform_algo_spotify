"""Cross-platform track-title matcher used by the PDF per-track scoping."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.utils.track_matching import track_title_matches as m


def test_apple_drops_original_suffix():
    assert m("Ô Chiotte l'arbitre Tucome Back - Original",
             "Ô Chiotte l'arbitre Tucome Back")


def test_soundcloud_prefix_and_freedownload():
    assert m("Kimono à semelle de fer",
             "1x7xxxxxxx - KIMONO À SEMELLE DE FER (free download)")


def test_accents_and_punctuation():
    assert m("Ca te dérange pas si je joue avec ton tapis_",
             "1x7xxxxxxx - Ca Te Dérange Pas Si Je Joue Avec Ton Tapis ?")


def test_base_does_not_match_remix():
    assert not m("Kimono à semelle de fer",
                 "1x7xxxxxxx - Kimono À Semelle De Fer (REMIX) Free Download")


def test_remix_matches_remix():
    assert m("Kimono à semelle de fer - Remix",
             "1x7xxxxxxx - Kimono À Semelle De Fer (REMIX)")


def test_unrelated_is_false():
    # ⚠️ **CE TEST CROYAIT COUVRIR LE CAS COURT, ET NE LE COUVRAIT PAS.** Son titre de
    # requête est LONG (« Kimono à semelle de fer ») : aucune inclusion possible, donc il
    # passait quel que soit le prédicat. Aucun cas du fichier n'exerçait un titre court
    # avant le 2026-09-20 — et c'est exactement là que vivait le défaut.
    assert not m("Kimono à semelle de fer", "HOUSE MUSIC MIX #3 BACK TO OLD SCHOOL")


@pytest.mark.parametrize("court,long_", [
    ("Mix", "HOUSE MUSIC MIX #3 BACK TO OLD SCHOOL"),   # similarité 0,1125
    ("Sun", "Sunset Boulevard"),                        # 0,1579
    ("Solo", "Solomon Dream"),                          # 0,2353
    ("Nuit", "La nuit de tous les dangers"),            # 0,1500
])
def test_a_short_title_does_not_match_by_substring(court, long_):
    """LE DÉFAUT — 2026-09-20 (R140 §16.1).

    `qb in cb or cb in qb` était une inclusion par SOUS-CHAÎNE en booléen dur, qui ne
    pèse jamais ce qui reste dehors. Les quatre cas ci-dessous rendaient `True`, à des
    similarités de **0,11 à 0,24**.

    Les SIX sites d'appel sont dans le PDF (`pdf_exporter/_collectors.py:292,412,435,
    842,864,890`), tous sous `single_song` : un artiste qui demande le PDF d'un seul
    morceau au titre COURT recevait les chiffres d'un autre.

    ⚠️ Le frère de la même famille (`track_mapping_suggest.title_similarity`) avait été
    réparé le **2026-09-06** et pèse la couverture depuis. Deux implémentations d'une
    même question, l'une corrigée, l'autre non.
    """
    assert not m(court, long_)


@pytest.mark.parametrize("court,long_", [
    ("Blue Sky", "Blue Sky Reprise"),      # similarité 0,6000
    ("Reves", "Reves lucides"),            # 0,4500
    ("Interlude", "Interlude II"),         # 0,4500
    ("Chemin", "Le Chemin"),               # 0,4500
])
def test_a_real_containment_still_matches(court, long_):
    """FAUX POSITIF fabriqué : resserrer ne doit pas casser l'inclusion LÉGITIME.

    Sans cette moitié, un prédicat qui refuse TOUTE inclusion passerait le test
    ci-dessus — et le PDF d'un morceau ne trouverait plus jamais sa variante.

    Le seuil est posé au milieu de l'intervalle vide : maximum des faux **0,2353**,
    minimum des vrais **0,4500**, seuil **0,35** — à 0,11 de chaque bord. Posé sur un
    bord, il aurait basculé au premier titre un peu différent.
    """
    assert m(court, long_)


def test_empty_is_false():
    assert not m("", "anything")
    assert not m("song", "")
