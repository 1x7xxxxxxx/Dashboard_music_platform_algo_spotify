"""Le titre de la barre latérale et les deux flèches de page en page.

Type: Sub
Uses: streamlit, nav_badges._neighbour_pages, navigation.goto
Triggers: app.render_navigation
Persists in: st.session_state['_nav_page'] (via `goto`)

POURQUOI UN MODULE — 2026-09-22
--------------------------------
Sorti d'`app.py` par le cliquet de longueur : ce fichier est gelé à **997 lignes**, et
le pourcentage d'avancement de la configuration l'a fait passer à 1 015. La règle du
cliquet est « ce qui entre dans ce fichier doit en faire sortir autant », et ce bloc
était le meilleur candidat — quarante-cinq lignes cohésives dont trente d'essai sur des
pixels mesurés au navigateur, qui ont leur place à côté du `<div>` qu'elles décrivent et
non au milieu du routage.

C'est le même mouvement, par le même cliquet, que `_neighbour_pages` le matin même.
"""
from __future__ import annotations

import html as _html

import streamlit as st

from src.dashboard.utils.i18n import t
from src.dashboard.utils.nav_badges import _neighbour_pages


def render_nav_header(rendered, is_locked) -> None:
    """Dessine « 🎵 Navigation » et les deux flèches, alignés sur la même ligne."""
    # Le titre, et deux flèches pour passer d'une page à la suivante sans chercher
    # dans une liste de quarante entrées. Demandé le 2026-09-04 : « rajoute 2 flèches
    # cliquables qui passent d'un onglet à l'autre à côté de NAVIGATION ».
    #
    # Écrire `_nav_page` ici est LÉGAL et ne l'est pas partout : on est dans la phase
    # barre latérale, avant que les radios de section soient instanciés — c'est
    # exactement la contrainte documentée dans `utils/navigation.py`. Le rerun qui
    # suit fait accorder le menu par `resolve_nav_page`.
    _cur = st.session_state.get('_nav_page', 'home')
    _prev, _next = _neighbour_pages(rendered, _cur, is_locked)

    # `vertical_alignment="center"` et un `###` plutôt qu'un `st.title`.
    #
    # Un `st.title` mesure ~2,5 fois la hauteur d'un bouton et porte sa propre marge
    # haute ; les colonnes s'alignant par le HAUT, les deux flèches flottaient contre
    # le sommet du titre, très au-dessus de sa ligne de base. « Pas alignées avec
    # Navigation, c'est moche » — 2026-09-04, et c'est exact : rien ne les alignait.
    #
    # Deux corrections, pas une. L'alignement centre les trois colonnes sur la même
    # ligne médiane ; le titre passe en `###` pour que cette ligne médiane soit à peu
    # près la hauteur d'un bouton — centrer un titre trois fois trop haut aurait
    # laissé les flèches au milieu d'un grand vide.
    try:
        _c_title, _c_prev, _c_next = st.sidebar.columns(
            [5, 1, 1], vertical_alignment="center")
    except TypeError:      # Streamlit < 1.36 — pas d'alignement vertical
        _c_title, _c_prev, _c_next = st.sidebar.columns([5, 1, 1])
    # Le titre reçoit la HAUTEUR d'un bouton, et s'y centre lui-même.
    #
    # Mesuré au navigateur, parce que deux tentatives ont raté avant celle-ci. Un
    # `st.title` place les flèches ~25 px au-dessus de sa ligne de base (colonnes
    # alignées par le haut). `vertical_alignment="center"` + un `###` laisse encore
    # 8 px, et la mesure dit pourquoi : le conteneur `stMarkdown` du titre est haut
    # de **13 px** alors que le `<h3>` qu'il porte en fait **29** — le titre déborde
    # de la boîte que Streamlit centre. Mettre la marge à zéro n'y change rien : ce
    # n'est pas la marge qui est fausse, c'est la hauteur mesurée.
    #
    # On cesse donc de compenser et on égalise : une boîte de 40 px — la hauteur
    # d'un bouton Streamlit — qui centre son propre texte. Les deux colonnes ont
    # alors la même hauteur de contenu, et l'alignement est vrai quelle que soit la
    # façon dont Streamlit la calcule. C'est NOTRE balise, pas un `<style>` visant
    # ses classes internes (`st-emotion-cache-…` change sans prévenir).
    #
    # Le `-16px` est MESURÉ, et sa valeur a une raison qui vaut d'être écrite : à
    # hauteurs égales (40 px des deux côtés, Streamlit 1.54), le bloc de texte
    # commençait 8 px plus bas que le bouton. Une compensation de -8 px n'en a
    # rattrapé que 4 — `vertical_alignment="center"` recentre APRÈS la marge, donc
    # il en amortit la moitié. Il faut le double de l'écart observé.
    #
    # Pour le remesurer un jour : comparer `getBoundingClientRect()` du div ci-
    # dessous et d'une flèche, et mettre ici deux fois l'écart des centres. Trop
    # petit pour valoir un test — un test de pixels casse à chaque montée de
    # version et n'apprendrait rien de plus que l'œil.
    _c_title.markdown(
        '<div style="height:40px;margin-top:-16px;display:flex;align-items:center;'
        'font-size:1.25rem;font-weight:600;">'
        + _html.escape(t("nav.title", "🎵 Navigation")) + '</div>',
        unsafe_allow_html=True)
    from src.dashboard.utils.navigation import goto
    if _c_prev.button("◀", key="_nav_prev", disabled=_prev is None,
                      help=t("nav.prev", "Page précédente"),
                      width="stretch"):
        goto(_prev)
    if _c_next.button("▶", key="_nav_next", disabled=_next is None,
                      help=t("nav.next", "Page suivante"),
                      width="stretch"):
        goto(_next)
