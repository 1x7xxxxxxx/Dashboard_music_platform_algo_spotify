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

# La largeur utile d'UNE colonne, estimée basse. Les guides sont rendus par paires
# (`st.columns(_COLS)`), donc chacun dispose d'environ la moitié de la zone de contenu
# — ~340 px sur la mise en page par défaut, moins l'espacement et la marge de
# l'expander qui les contient.
#
# Le plafond était de 720 px, hérité de l'époque où un guide occupait toute la
# largeur. Depuis la mise en colonnes, toute capture plus large que sa colonne
# DÉBORDE du cadre — signalé le 2026-09-06 (« certaines captures dépassent du cadre,
# c'est pas beau »), et mesuré : sur 16 captures, 8 font entre 1257 et 1693 px.
_COLUMN_WIDTH_PX = 300


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

    # REPLIÉES par défaut (demandé le 2026-09-06). Elles étaient dépliées depuis que
    # la mise en colonnes les faisait tenir toutes les deux à l'écran — mais dépliées,
    # elles poussent la page sur plusieurs écrans de captures avant qu'on ait vu ce
    # qu'il y a en dessous, alors que la zone de dépôt est juste au-dessus et que la
    # plupart des visites reviennent y déposer un fichier, pas relire la notice.
    _render_in_columns(platforms, expanded=False)

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
            render_bounded_image(path, step.caption)
        # else: missing screenshot — show nothing (step text still stands)


def render_bounded_image(path, caption=None) -> None:
    """Jamais plus large que sa colonne, jamais agrandie non plus.

    Les deux modes de laideur sont opposés et il faut les éviter tous les deux :
    une capture de 1693 px dans une colonne de ~340 px déborde du cadre ; une
    vignette de 138 px étirée à la colonne devient floue. Aucun réglage unique ne
    règle les deux, parce que Streamlit ne dit pas au Python la largeur du conteneur.

    D'où la règle : au-dessus de la largeur estimée d'une colonne, on laisse
    Streamlit ajuster (ce qui ne peut être qu'une RÉDUCTION) ; en dessous, on rend la
    taille native (ce qui ne peut pas déborder). L'estimation est volontairement
    basse : se tromper vers le bas rend une image un peu petite, se tromper vers le
    haut la fait dépasser — et c'est ce qu'on corrige.
    """
    # `width="stretch"` et non `use_container_width=True` : ce second est retiré de
    # Streamlit depuis fin 2025 et lève ici (1.54). La page entière tombait en erreur,
    # pas seulement l'image — vu au rendu, jamais à la lecture du code.
    native = _native_width(path)
    if native is None or native > _COLUMN_WIDTH_PX:
        st.image(str(path), caption=caption, width="stretch")
    else:
        st.image(str(path), caption=caption, width=native)


def _native_width(path):
    """Largeur réelle du fichier, ou `None` si on ne peut pas la lire."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.width
    except Exception:  # noqa: BLE001 — illisible : on laisse Streamlit ajuster
        return None


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
