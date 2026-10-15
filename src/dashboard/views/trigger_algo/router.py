"""trigger_algo — router: the slim show() entry point.

R570 (owner, 2026-10-15) : the releases picked in the catalogue drive the whole page —
R579: a reference and a comparison filter, newest and second-newest by default; two parts, « Où en sont mes titres » then « Une fois
déclenché ». The title selectbox, the period filter, the per-track coach, the budget/ROI
part and the CPR cards are gone.
"""
import streamlit as st

from src.dashboard.utils import view_session
from src.dashboard.utils.i18n import t

from ._custom_window_entry import render_custom_grid
from ._forecast import show_forecast
from ._outcome_entry import render_outcomes
from ._sections import arrival_section, guide_sections_md, is_alias_arrival, section_label
from ._tab_algo_streams import release_date
from ._tab_catalogue import _show_tab_catalogue


def show():
    from src.dashboard.auth import require_plan
    if not require_plan('premium'):
        return

    st.title(t("trigger_algo.title", "🚀 Prédiction déclenchement algos Spotify"))
    st.markdown(t("trigger_algo.subtitle",
                  "Tes deux dernières sorties : où elles en sont, ce qui déclenche chaque playlist, et leurs écoutes à venir."))

    with st.expander(t("trigger_algo.guide_expander",
                       "📖 Comment lire cette page (guide artiste) — à ouvrir une fois"),
                     expanded=False):
        st.markdown(t(
            "trigger_algo.guide_body",
            "Cette page répond à **une seule question** : *« Spotify va-t-il pousser mon "
            "titre tout seul dans ses algorithmes ? »* Les **28 premiers jours** après la "
            "sortie (J+28) sont décisifs — c'est la fenêtre où les algorithmes décident.\n\n"

            "**🎚️ Les 3 algorithmes suivis**\n"
            "- 💎 **Discover Weekly (DW)** — playlist perso hebdomadaire envoyée à des auditeurs "
            "qui ne te connaissent PAS encore. C'est la découverte pure, le Graal pour gagner de "
            "nouveaux fans. La porte la plus dure à ouvrir.\n"
            "- 📻 **Radio** — flux algorithmique « infini » qui enchaîne des titres similaires. "
            "Signe que Spotify te juge « fiable » pour nourrir ses recommandations. Demande le "
            "plus de volume de streams.\n"
            "- 📡 **Release Radar (RR)** — playlist hebdo poussée à **tes abonnés** à chaque "
            "sortie. Plus facile à déclencher (ils te suivent déjà), mais touche surtout ton "
            "audience existante.\n\n"

            "**🔢 Les 2 chiffres à NE PAS confondre**\n"
            "- **DW % / Radio % / RR %** = probabilité **absolue et calibrée** de déclenchement "
            "(50 % = vraiment 1 chance sur 2). C'est LA mesure de ta vraie chance. Bandes de "
            "décision : 🔴 < 20 % **STOP** · 🟠 20–50 % **OPTIMISER** · 🟢 ≥ 50 % **SCALER**.\n"
            # ⚠️ LE « SCORE /20 » EST RETIRÉ — 2026-09-22. Il étirait en min-max sur
            # une échelle de 20 un écart de probabilité de 0,36 point, mesuré sur les
            # dix titres de l'artiste 1. Il fabriquait l'apparence d'un classement à
            # partir d'une donnée qui n'en portait aucun — c'est-à-dire exactement ce
            # qu'il prétendait offrir. Sa prose le disait déjà : « un titre peut être
            # 20/20 avec seulement 10 % de proba réelle ».
            "- ⚠️ **Une probabilité proche de 6,5 % (DW/RR) ou 10,7 % (Radio) est le "
            "PLANCHER de la calibration** : elle veut dire que le modèle a rendu zéro, "
            "pas qu'il hésite. Deux titres posés dessus ne se comparent pas.\n\n"

            "**🧭 Les notions clés**\n"
            "- **Popularity Index (0–100)** — la « note de popularité » Spotify du titre. C'est "
            "la porte d'entrée : chaque algo a un PI minimum. Plus ton PI monte, plus les portes "
            "s'ouvrent.\n"
            "- **Seuils elbow (28j)** — volume d'algo-streams **générés par la playlist "
            "elle-même** qui marque le *début* d'un trigger : **~137 (DW)**, **~639 (Radio)**, "
            "**~130 (RR)**. C'est le minimum que la playlist produit une fois déclenchée — "
            "**pas** le nombre de streams à générer soi-même pour la déclencher.\n"
            "- **Velocity (momentum)** — vitesse d'accélération récente des streams. Un titre qui "
            "monte vite est favorisé ; un titre à plat stagne.\n"
            "- **Discovery Mode** — option Spotify (commission sur tes royalties) qui force "
            "l'entrée en Radio. À activer ou non selon le contexte du titre.\n\n"

            "⚠️ **Limite honnête** : le modèle prédit BIEN *si* un titre va déclencher "
            "(classification, AUC ~0.92), mais MAL *combien* de streams il fera (le volume n'est "
            "pas fiable). **Fie-toi aux %, pas aux prévisions de volume en €.**"
        ))
        # R380 : the parts are listed from the tuple the layout reads — this list
        # announced seven tabs for four, after two hand rewrites.
        st.markdown(guide_sections_md())

    _say_where_the_alias_lands()
    from src.dashboard.utils.fragment_db import page_db_scope

    # `page_db_scope` : any fragment the page renders borrows this connection (rule 9).
    with view_session() as (db, artist_id), page_db_scope(db, artist_id):
        _section("catalogue", first=True)
        choix = _show_tab_catalogue(db, artist_id)
        # R584 — both titles on ONE forecast; R583 moved the estimates beside the gauges.
        show_forecast(db, artist_id, [(s_, release_date(db, artist_id, s_)) for s_ in choix])
        _section("declenche")
        render_outcomes(db, artist_id, tracks=choix or None)
        render_custom_grid(db, artist_id, tracks=choix or None)


def _section(key: str, *, first: bool = False) -> None:
    """One part of the page: a separator, then its title — anchored by its key."""
    if not first:
        st.divider()
    st.header(section_label(key), anchor=key)


def _say_where_the_alias_lands() -> None:
    """A former page's link (mail, PDF) lands here: say where its content now is."""
    from src.dashboard.routes import ALIAS_ARRIVAL_KEY
    from src.dashboard.utils.navigation import pop_goto_alias

    # R525 — an in-app `goto(alias)` drops `?page=`, so the URL arrival is empty: the
    # alias it was called with is kept for this one run instead.
    alias = st.session_state.get(ALIAS_ARRIVAL_KEY) or pop_goto_alias()
    if not is_alias_arrival(alias):
        return
    key = arrival_section(alias)
    if key is None:
        st.info(t("trigger_algo.alias_landing_page",
                  "Cette page fait désormais partie de « Prédiction déclenchement algos "
                  "Spotify »."))
        return
    st.info(t("trigger_algo.alias_landing",
              "Cette page fait désormais partie de « Prédiction déclenchement » : "
              "[↓ aller à la section {section}](#{anchor})").format(
        section=section_label(key), anchor=key))
