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


# Les deux plateformes que l'artiste vient chercher, côte à côte : Spotify for
# Artists à GAUCHE, Apple Music à DROITE (demandé le 2026-09-06). Les distributeurs
# suivent en dessous — ils ne concernent pas tout le monde, et les empiler tous les
# quatre faisait défiler la page avant d'avoir vu la seconde.
_SIDE_BY_SIDE = ("s4a", "apple")


def render_csv_guides() -> None:
    """Render one expander per platform with download steps + expected-CSV table."""
    st.markdown(t("csv_guides.intro_heading",
                  "**Comment télécharger puis importer vos fichiers ?**"))
    by_key = {g.key: g for g in CSV_GUIDES}
    paired = [by_key[k] for k in _SIDE_BY_SIDE if k in by_key]
    rest = [g for g in CSV_GUIDES if g.key not in _SIDE_BY_SIDE]

    # Les deux principaux sont OUVERTS : côte à côte, ils tiennent tous les deux à
    # l'écran, donc plus rien ne justifie d'en cacher un. Empilés, le premier seul
    # s'ouvrait — et les deux artistes qui ont atteint cette page n'ont jamais
    # déplié les suivants.
    for col, guide in zip(st.columns(2), paired):
        with col:
            _render_guide_expander(guide, expanded=True)

    # Les distributeurs restent repliés : ils ne concernent qu'une partie des
    # artistes (Cooper, About Face, p.271 — divulgation progressive).
    for row_start in range(0, len(rest), 2):
        for col, guide in zip(st.columns(2), rest[row_start:row_start + 2]):
            with col:
                _render_guide_expander(guide, expanded=False)


def _render_guide_expander(guide: PlatformGuide, expanded: bool = False) -> None:
    label = t("csv_guides.expander_suffix",
              "{icon} {title} — télécharger & importer").format(
        icon=guide.icon, title=guide.title)
    with st.expander(label, expanded=expanded):
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
