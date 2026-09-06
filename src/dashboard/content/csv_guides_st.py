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
    FAMILY_DISTRIBUTOR,
    FAMILY_PLATFORM,
    ExpectedCsv,
    GuideStep,
    PlatformGuide,
    screenshot_path,
)
from src.dashboard.utils.i18n import t

# Max display width (px). Streamlit's "content"/"stretch" both upscale small crops
# to the column → blur. Capping to the native width avoids any upscaling.
_MAX_IMG_WIDTH = 720


# La mise en page est DÉRIVÉE de `PlatformGuide.family`, jamais d'une liste de clés
# tapée ici. La constante `_SIDE_BY_SIDE = ("s4a", "apple")` qui tenait ce rôle
# jusqu'au 2026-09-06 rangeait tout le reste en « distributeurs » par défaut : un
# guide ajouté demain aurait pris ce titre sans que personne l'ait décidé, et la
# page ne l'aurait jamais signalé. Voir `csv_guides.FAMILY_PLATFORM`.
_COLS = 2


def render_csv_guides() -> None:
    """Les types acceptés, en colonnes, sous l'unique zone de dépôt.

    Une seule zone de dépôt et plusieurs colonnes de TYPES : le fichier est reconnu
    tout seul, donc l'artiste n'a rien à classer avant de déposer — les colonnes
    lui disent seulement où aller chercher quoi. C'est la demande du 2026-09-06,
    et c'est aussi ce que la détection automatique permet : classer serait une
    décision que le code prend mieux que lui.
    """
    st.markdown(t("csv_guides.intro_heading",
                  "**Comment télécharger puis importer vos fichiers ?**"))

    platforms = [g for g in CSV_GUIDES if g.family == FAMILY_PLATFORM]
    distributors = [g for g in CSV_GUIDES if g.family == FAMILY_DISTRIBUTOR]

    # Les plateformes d'écoute, côte à côte et DÉPLIÉES : elles tiennent toutes les
    # deux à l'écran, donc plus rien ne justifie d'en cacher une. Empilées, seule la
    # première s'ouvrait — et les deux artistes qui ont atteint cette page n'ont
    # jamais déplié les suivantes.
    _render_in_columns(platforms, expanded=True)

    # Les distributeurs, TOUT EN BAS et en UN SEUL bloc (demandé le 2026-09-06).
    # Ils ne concernent qu'une partie des artistes et ne parlent pas d'écoutes mais
    # de revenus : deux volets de même rang que Spotify et Apple donnaient à un
    # sujet minoritaire la moitié de la page. Divulgation progressive — Cooper,
    # About Face, p.271.
    if distributors:
        st.markdown("---")
        with st.expander(t("csv_guides.distributor_group",
                           "💿 Mon distributeur (revenus) — iMusician, DistroKid…"),
                         expanded=False):
            st.caption(t(
                "csv_guides.distributor_help",
                "Uniquement si vous voulez suivre vos **revenus**. Ces fichiers ne "
                "contiennent pas d'écoutes : ils n'ont aucun effet sur vos "
                "statistiques Spotify ou Apple."))
            _render_in_columns(distributors, expanded=False, nested=True)


def _render_in_columns(guides: list[PlatformGuide], *, expanded: bool,
                       nested: bool = False) -> None:
    """`_COLS` par ligne, dans l'ordre de déclaration de `CSV_GUIDES`."""
    for start in range(0, len(guides), _COLS):
        for col, guide in zip(st.columns(_COLS), guides[start:start + _COLS]):
            with col:
                _render_guide_expander(guide, expanded=expanded, nested=nested)


def _render_guide_expander(guide: PlatformGuide, expanded: bool = False,
                           nested: bool = False) -> None:
    label = t("csv_guides.expander_suffix",
              "{icon} {title} — télécharger & importer").format(
        icon=guide.icon, title=guide.title)
    # Streamlit interdit un expander DANS un expander : à l'intérieur du bloc
    # distributeurs, le volet devient un titre. Écrit ici plutôt que chez l'appelant
    # parce que c'est une contrainte du widget, pas une décision de mise en page.
    if nested:
        st.markdown(f"**{label}**")
        _render_guide_body(guide)
        return
    with st.expander(label, expanded=expanded):
        _render_guide_body(guide)


def _render_guide_body(guide: PlatformGuide) -> None:
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
