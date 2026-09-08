"""La période affichée sur l'accueil — choisie une fois, lue par les deux sections.

Type: Utility
Uses: streamlit
Triggers: views/home._section_streams, views/home._section_platform_trend
Persists in: st.session_state

Demandé le 2026-09-08 : « un filtre de date intelligent qui sélectionne d'office depuis
le début, avec sélecteur cette année etc. Ce sélecteur intervient dans les streams
totaux et évolution par plateforme ».

**Un seul propriétaire du réglage.** Les deux sections le LISENT, aucune ne l'écrit :
deux sélecteurs pour une même période se réécrivent l'un l'autre à chaque rerun, et ce
dépôt l'a déjà payé avec les deux sélecteurs de langue (`utils/i18n`, 2026-09-05).

Ce que « depuis le début » veut dire, et pourquoi ce n'est pas une fenêtre
------------------------------------------------------------------------
Ce n'est pas « une très grande fenêtre », et les confondre donnerait des chiffres faux.

* **Depuis le début** : les totaux sont ceux que les plateformes annoncent
  aujourd'hui — le compteur de vues d'une chaîne, le cumul de lectures d'un titre.
  Ils portent tout ce qui précède notre première collecte.
* **Une période bornée** : on ne peut additionner que ce qu'on a MESURÉ, donc la somme
  des écarts quotidiens sur ces jours-là. Un compteur cumulatif ne dit pas ce qui s'est
  passé avant qu'on le regarde.

Le second est donc structurellement plus petit que le premier, et ce n'est pas une
perte de données : c'est la seule chose qu'on puisse affirmer. `RANGE_NOTE` porte cette
phrase pour que l'écart ne se lise pas comme un bug.
"""
from __future__ import annotations

import datetime as _dt

import streamlit as st

_KEY = "_home_range"

# L'ordre est celui du sélecteur. `None` = pas de borne — « depuis le début ».
# Les libellés sont volontairement courts : ils vivent dans une barre horizontale.
RANGES: dict = {
    "all": (None, "Depuis le début"),
    "ytd": ("ytd", "Cette année"),
    "12m": (365, "12 mois"),
    "90d": (90, "90 jours"),
    "30d": (30, "30 jours"),
}

DEFAULT = "all"


def current_key() -> str:
    """La période choisie, `all` par défaut — jamais une exception hors Streamlit."""
    try:
        key = st.session_state.get(_KEY)
    except Exception:      # noqa: BLE001 — appelé depuis un test headless
        return DEFAULT
    return key if key in RANGES else DEFAULT


def bounds(key: str | None = None, today: _dt.date | None = None):
    """(premier jour inclus, dernier jour inclus) — `(None, None)` pour « depuis le début ».

    `today` est injectable pour que le garde n'ait pas à dépendre du calendrier du jour
    où il tourne : un test qui lit l'horloge change de verdict tout seul le 1er janvier.
    """
    key = key or current_key()
    span = RANGES.get(key, RANGES[DEFAULT])[0]
    if span is None:
        return None, None
    day = today or _dt.date.today()
    if span == "ytd":
        return _dt.date(day.year, 1, 1), day
    return day - _dt.timedelta(days=span - 1), day


def is_bounded(key: str | None = None) -> bool:
    return bounds(key)[0] is not None


def label(key: str | None = None) -> str:
    return RANGES.get(key or current_key(), RANGES[DEFAULT])[1]


def render_selector(*, key: str = "_home_range_widget") -> str:
    """Dessine le sélecteur et rend la période choisie.

    `st.segmented_control` plutôt qu'un `st.radio` : c'est une barre, pas une liste, et
    c'est déjà la forme employée par la barre d'onglets de Credentials. Un repli sur
    `st.radio` couvre les versions de Streamlit qui ne le portent pas — la page ne doit
    pas disparaître pour un widget.
    """
    labels = {k: v[1] for k, v in RANGES.items()}
    options = list(RANGES)
    current = current_key()
    try:
        chosen = st.segmented_control(
            "Période", options, format_func=lambda k: labels[k],
            default=current, key=key, label_visibility="collapsed")
    except Exception:      # noqa: BLE001 — Streamlit < 1.40
        chosen = st.radio(
            "Période", options, index=options.index(current), horizontal=True,
            format_func=lambda k: labels[k], key=key, label_visibility="collapsed")
    chosen = chosen or current
    st.session_state[_KEY] = chosen
    return chosen


RANGE_NOTE = (
    "Sur une période bornée, les totaux sont la somme de ce qu'on a **mesuré** jour "
    "après jour. « Depuis le début » affiche les compteurs des plateformes, qui "
    "incluent tout ce qui précède notre première collecte — c'est pour ça qu'ils sont "
    "plus élevés."
)
