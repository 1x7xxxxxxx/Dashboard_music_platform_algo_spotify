"""Where the pre-rendered onboarding guide PDF lives, per language.

Type: Utility
Uses: src.utils.config_loader
Depends on: nothing under src/dashboard
Persists in: nothing (docs/guides/ is written by src.dashboard.guides.guide_pdf)

The welcome mail (`src/utils/verification_email.py`) attaches this file; reading the
path from `src.dashboard.guides.guide_pdf` pulled the whole PDF renderer — WeasyPrint
included — into a low layer just to compute a file name (R626, arc 6).
"""
from __future__ import annotations

from pathlib import Path


def output_pdf_path(lang: str = "fr") -> Path:
    """FR → onboarding_guide.pdf (default); EN → onboarding_guide_en.pdf."""
    from src.utils.config_loader import config_loader
    name = "onboarding_guide.pdf" if lang == "fr" else f"onboarding_guide_{lang}.pdf"
    return config_loader.project_root / "docs" / "guides" / name
