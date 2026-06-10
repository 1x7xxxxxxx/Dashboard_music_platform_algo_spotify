"""Snapshot + unit tests — pdf_exporter.render_html.

render_html is pure string-building (no DB, no PDF lib), so we lock its exact
output against a golden file. This is the byte-identical net for the R5 refactor
(extracting the _kpi_card / _html_table primitives must not change one byte).

freshness_status is now-relative, so it is monkeypatched to a constant to keep
the golden deterministic across days.
"""
import os
from datetime import datetime, date

import pytest

from src.dashboard.utils import pdf_exporter

GOLDEN = os.path.join(os.path.dirname(__file__), "fixtures", "pdf_report_golden.html")


def _sample_data():
    """A fully-populated report data dict exercising every _render_* branch."""
    dt = datetime(2026, 1, 15, 9, 30, 0)
    last = datetime(2026, 1, 14, 8, 0, 0)
    return {
        "generated_at": dt,
        "from_date": date(2025, 1, 1),
        "to_date": date(2026, 1, 1),
        "freshness": {
            "Spotify S4A": {"icon": "🎵", "last_dt": last},
            "YouTube": {"icon": "🎬", "last_dt": last},
        },
        "streams": {"s4a": 12000, "youtube": 8000, "soundcloud": 3000,
                    "apple": 1500, "total": 24500},
        "spotify_popularity": {"score": 42, "track": "Hit Song"},
        "instagram": {"followers": 5000, "date": "2026-01-14"},
        "soundcloud_likes": 320,
        "roi": {"roi_pct": 18.4, "profitable": True,
                "revenue_eur": 210.5, "meta_spend": 80.0},
        "s4a_top_songs": [("Song A", 9000, 700), ("Song B", 3000, 120)],
        "youtube_data": {
            "subscriber_count": 1500, "total_views": 250000,
            "videos": [("Clip 1", "2025-12-01", 40000, 1200, 80)],
        },
        "instagram_data": {
            "followers": 5000, "username": "artist", "media_count": 120,
            "history": [("2026-01-13", 4980), ("2026-01-14", 5000)],
        },
        "meta_data": {
            "total_spend": 80.0, "total_results": 42,
            "campaigns": [("Campagne 1", 80.0, 42, 50000, 30000, 900)],
        },
        "sc_tracks": [("Track X", 3000, 200, 15, 8)],
        "apple_data": {
            "total_plays": 1500, "total_shazams": 60,
            "top_songs": [("Song A", 1200)],
        },
        "songs_data": [{
            "song": "Hit Song", "total_streams": 9000, "last7d_streams": 700,
            "ml": {"dw_prob": 0.62, "rr_prob": 0.31, "radio_prob": 0.12,
                   "dw_forecast": 5400, "rr_forecast": 1200,
                   "prediction_date": "2026-01-14"},
        }],
    }


@pytest.fixture(autouse=True)
def _freeze_freshness(monkeypatch):
    monkeypatch.setattr(pdf_exporter, "freshness_status",
                        lambda _dt: ("🟢", None, "à jour"))


def test_render_html_matches_golden():
    html = pdf_exporter.render_html(_sample_data(), "Test Artist")
    with open(GOLDEN, encoding="utf-8") as fh:
        expected = fh.read()
    assert html == expected, "render_html output drifted from the golden snapshot"


def test_empty_sections_render_no_data_guards():
    data = _sample_data()
    data["youtube_data"] = None
    data["meta_data"] = None
    data["s4a_top_songs"] = []
    html = pdf_exporter.render_html(data, "Test Artist")
    assert html.count("no-data") >= 3
    assert "Aucune donnée YouTube disponible." in html
    assert "Aucune donnée Meta Ads disponible." in html


def test_render_html_english_translates():
    """lang='en' produces an English report — locks in PDF bilinguality.
    FR remains the byte-identical golden (default); EN is asserted by markers
    rather than a second golden (avoids maintaining two snapshots)."""
    html = pdf_exporter.render_html(_sample_data(), "Test Artist", lang="en")
    assert '<html lang="en">' in html
    for fr in ("Abonnés", "Dépenses totales", "Rapport artiste",
               "Généré automatiquement", "Aucune donnée"):
        assert fr not in html, f"untranslated FR string leaked into EN report: {fr!r}"
    for en in ("Subscribers", "Artist report", "Generated automatically"):
        assert en in html, f"expected English string missing: {en!r}"
