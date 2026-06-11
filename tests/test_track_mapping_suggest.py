"""Unit tests for the cross-platform track-link suggestion engine (pure, DB-free)."""
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.track_mapping_suggest import (  # noqa: E402
    W_CAMP_DATE,
    W_CAMP_TITLE,
    confidence_badge,
    date_proximity,
    mapping_boost,
    rank_campaign_candidates,
    rank_track_candidates,
    title_similarity,
)


# ── title_similarity ────────────────────────────────────────────────────────
def test_title_similarity_exact_after_normalize():
    assert title_similarity("Kimono à semelle de fer",
                            "KIMONO A SEMELLE DE FER") == 1.0


def test_title_similarity_containment_artist_prefix():
    s = title_similarity("1x7xxxxxxx - Kimono à semelle de fer (free download)",
                         "Kimono à semelle de fer")
    assert s >= 0.85


def test_title_similarity_base_vs_remix_is_zero():
    assert title_similarity("Kimono à semelle de fer",
                            "Kimono à semelle de fer (Remix)") == 0.0


def test_title_similarity_remix_vs_remix_high():
    assert title_similarity("Kimono - Remix", "Kimono (Remix)") >= 0.8


def test_title_similarity_unrelated_low():
    assert title_similarity("Kimono", "Totally Different Song") < 0.3


def test_title_similarity_empty_is_zero():
    assert title_similarity("", "Kimono") == 0.0
    assert title_similarity("Kimono", "") == 0.0


# ── date_proximity ──────────────────────────────────────────────────────────
def test_date_proximity_same_day_is_one():
    d = date(2025, 3, 1)
    assert date_proximity(d, d) == 1.0


def test_date_proximity_halflife():
    assert abs(date_proximity(date(2025, 3, 15), date(2025, 3, 1)) - 0.5) < 0.02


def test_date_proximity_monotonic_decay():
    base = date(2025, 1, 1)
    p7 = date_proximity(date(2025, 1, 8), base)
    p30 = date_proximity(date(2025, 1, 31), base)
    p90 = date_proximity(date(2025, 4, 1), base)
    assert p7 > p30 > p90
    assert p90 < 0.05


def test_date_proximity_accepts_datetime_and_missing():
    assert date_proximity(datetime(2025, 3, 1, 9, 0), date(2025, 3, 1)) == 1.0
    assert date_proximity(None, date(2025, 3, 1)) == 0.0
    assert date_proximity(date(2025, 3, 1), None) == 0.0


# ── mapping_boost ───────────────────────────────────────────────────────────
def test_mapping_boost():
    assert mapping_boost("kimono", {"kimono", "autre"}) == 1.0
    assert mapping_boost("kimono", set()) == 0.0


# ── ranking ─────────────────────────────────────────────────────────────────
_TRACKS = [
    {"match_key": "kimono a semelle de fer", "title": "Kimono à semelle de fer",
     "release_date": date(2024, 5, 1)},
    {"match_key": "je ne parle pas", "title": "Je ne parle pas très bien le français",
     "release_date": date(2024, 4, 1)},
    {"match_key": "autre titre", "title": "Un autre titre", "release_date": date(2023, 1, 1)},
]


def test_rank_track_candidates_exact_first():
    out = rank_track_candidates("KIMONO A SEMELLE DE FER", _TRACKS, top_n=3)
    assert out and out[0].match_key == "kimono a semelle de fer"
    assert out[0].method == "exact" and out[0].score == 1.0


def test_rank_track_candidates_top_n_truncates():
    out = rank_track_candidates("Kimono à semelle de fer", _TRACKS, top_n=1)
    assert len(out) == 1


def test_rank_campaign_date_term_flips_winner():
    # Campaign title weakly mentions neither track strongly; the date is far closer to
    # the "autre titre" release → the date term must change the winner vs title-only.
    camp = "Promo été 2023"
    start = date(2023, 1, 5)  # ~4 days from 'autre titre' (2023-01-01), far from others
    out = rank_campaign_candidates(camp, start, _TRACKS, top_n=3)
    assert out[0].match_key == "autre titre"
    assert out[0].method == "date_proximity"


def test_campaign_weights_sum_to_one():
    assert abs((W_CAMP_TITLE + W_CAMP_DATE) - 1.0) < 1e-9


# ── confidence_badge ────────────────────────────────────────────────────────
def test_confidence_badge_bands():
    assert confidence_badge(1.0) == "🟢"
    assert confidence_badge(0.8) == "🟢"
    assert confidence_badge(0.79) == "🟡"
    assert confidence_badge(0.5) == "🟡"
    assert confidence_badge(0.49) == "🔴"
    assert confidence_badge(0.13) == "🔴"   # junk title (DJ set / other artist)
    assert confidence_badge(0.0) == "🔴"
    assert confidence_badge(None) == "🔴"
