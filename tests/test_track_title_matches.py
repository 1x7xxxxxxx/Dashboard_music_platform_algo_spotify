"""Cross-platform track-title matcher used by the PDF per-track scoping."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
    assert not m("Kimono à semelle de fer", "HOUSE MUSIC MIX #3 BACK TO OLD SCHOOL")


def test_empty_is_false():
    assert not m("", "anything")
    assert not m("song", "")
