"""Streamlit renderer for the CSV guides (one of the two renderers; see csv_guides).

Type: Sub
Uses: streamlit, src.dashboard.content.csv_guides
Depends on: assets/csv_guides/*.png (optional — missing images degrade gracefully)
Persists in: nothing
"""
import pandas as pd
import streamlit as st

from src.dashboard.content.csv_guides import (
    CSV_GUIDES,
    ExpectedCsv,
    GuideStep,
    PlatformGuide,
    screenshot_path,
)
from src.dashboard.utils.i18n import t

# Max display width (px). Streamlit's "content"/"stretch" both upscale small crops
# to the column → blur. Capping to the native width avoids any upscaling.
_MAX_IMG_WIDTH = 720


def render_csv_guides() -> None:
    """Render one expander per platform with download steps + expected-CSV table."""
    st.markdown(t("csv_guides.intro_heading",
                  "**Comment télécharger puis importer vos fichiers ?**"))
    for guide in CSV_GUIDES:
        _render_guide_expander(guide)


def _render_guide_expander(guide: PlatformGuide) -> None:
    label = t("csv_guides.expander_suffix",
              "{icon} {title} — télécharger & importer").format(
        icon=guide.icon, title=guide.title)
    with st.expander(label, expanded=False):
        st.markdown(guide.intro)
        for i, step in enumerate(guide.steps, 1):
            _render_step(i, step)
        _render_expected_table(guide)


def _render_step(num: int, step: GuideStep) -> None:
    st.markdown(f"**{num}.** {step.text}")
    if step.screenshot:
        path = screenshot_path(step.screenshot)
        if path.exists():
            st.image(str(path), caption=step.caption, width=_display_width(path))
        # else: missing screenshot — show nothing (step text still stands)


def _display_width(path) -> int:
    """Native image width, capped — never upscales (avoids blur on small crops)."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return min(im.width, _MAX_IMG_WIDTH)
    except Exception:
        return _MAX_IMG_WIDTH


def _render_expected_table(guide: PlatformGuide) -> None:
    rows = [_expected_row(e) for e in guide.expected]
    st.caption(t("csv_guides.recognized_caption", "Fichiers reconnus automatiquement :"))
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def _expected_row(e: ExpectedCsv) -> dict:
    return {
        t("csv_guides.col_file", "Fichier"): e.label,
        t("csv_guides.col_expected_name", "Nom attendu"): e.filename_hint,
        t("csv_guides.col_columns", "Colonnes"): ", ".join(e.columns),
    }
