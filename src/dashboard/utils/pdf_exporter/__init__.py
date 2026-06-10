"""Génération de rapports PDF artiste via WeasyPrint (package split)."""
from src.dashboard.utils.kpi_helpers import freshness_status

from ._config import ALL_SECTIONS, PREMIUM_SECTIONS
from ._collectors import (
    get_available_songs, get_artists_list,
    _latest_release, _get_artist_name, _release_date,
)
from ._report import collect_report_data, render_html, generate_pdf

__all__ = [
    "ALL_SECTIONS", "PREMIUM_SECTIONS",
    "get_available_songs", "get_artists_list",
    "_latest_release", "_get_artist_name", "_release_date",
    "collect_report_data", "render_html", "generate_pdf",
    "freshness_status",
]
