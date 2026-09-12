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
perte de données : c'est la seule chose qu'on puisse affirmer.

`RANGE_NOTE` a porté cette phrase sous la figure de l'accueil jusqu'au 2026-09-10. Elle
a été RETIRÉE avec les tuiles qu'elle excusait : les deux nombres ne se côtoient plus,
donc il n'y a plus d'écart à expliquer. Une note qui rend une contradiction acceptable
n'est pas un correctif — c'est une contradiction qu'on a décidé de garder.
"""
from __future__ import annotations

import datetime as _dt

import streamlit as st

_KEY = "_home_range"

# L'ordre est celui du sélecteur. `None` = pas de borne — « depuis le début ».
# Les libellés sont volontairement courts : ils vivent dans une barre horizontale.
# « Cette année » a été RETIRÉE le 2026-09-12 — « c'est pareil non ? garde
# uniquement 12 mois ». Les deux ne sont pas identiques et c'est justement le
# problème : au 12 septembre, YTD couvre 255 jours et « 12 mois » 365, donc elles
# rendent presque la même figure ; au 5 janvier, l'une en couvre 5 et l'autre 365.
# Une option dont l'écart avec sa voisine dépend du MOIS où on la lit se choisit au
# hasard onze mois sur douze, et surprend le douzième.
#
# LE CALCUL PART AVEC L'ENTRÉE, et c'est délibéré. On a d'abord gardé la branche
# `span == "ytd"` « au cas où un signet la porte » — puis on l'a exécutée : comme la
# clé n'est plus dans `RANGES`, `bounds("ytd")` retombe sur le défaut et rend
# `(None, None)`. La branche était déjà inatteignable, et le commentaire qui la
# gardait affirmait le contraire. C'est « du code correct que rien n'atteint », la
# forme que ce dépôt paie le plus souvent — retirée plutôt que gardée.
#
# Conséquence assumée : un signet `?range=ytd` ouvre « Depuis le début ». C'est déjà
# ce que fait n'importe quelle clé inconnue, et `current_key` le dit depuis toujours.
RANGES: dict = {
    "all": (None, "Depuis le début"),
    "12m": (365, "12 mois"),
    "90d": (90, "90 jours"),
    "30d": (30, "30 jours"),
    "custom": ("custom", "📅 Sur mesure"),
}

DEFAULT = "all"

# Les bornes du choix « sur mesure », posées par le sélecteur de dates.
_CUSTOM_SINCE, _CUSTOM_UNTIL = "_home_range_from", "_home_range_to"


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
    day = today or _today_in_display_tz()
    if span == "custom":
        since, until = custom_bounds()
        # Tant que les deux dates ne sont pas posées, « sur mesure » ne borne rien :
        # afficher une fenêtre vide serait pire que ne pas filtrer.
        return (since, until) if since and until else (None, None)
    return day - _dt.timedelta(days=span - 1), day


def _today_in_display_tz() -> _dt.date:
    """La journée du PRODUIT, pas celle de l'hôte qui affiche.

    `_dt.date.today()` rend la date locale du serveur, qui n'a aucune raison d'être
    celle du lecteur ni celle des données. Les séries, elles, sont datées en UTC pour
    les sources API. Une borne posée sur une troisième horloge fait entrer ou sortir
    un jour entier de la fenêtre — et le 1ᵉʳ janvier, une année entière.

    On fixe donc la journée du produit sur `DISPLAY_TZ`, le fuseau dans lequel il est
    lu, déjà déclaré une fois pour toutes à côté.
    """
    try:
        from zoneinfo import ZoneInfo

        from src.dashboard.utils.tz import DISPLAY_TZ
        return _dt.datetime.now(ZoneInfo(DISPLAY_TZ)).date()
    except Exception:      # noqa: BLE001 — un fuseau absent ne fait pas tomber la page
        return _dt.date.today()


def custom_bounds():
    """Les deux dates saisies, ou `(None, None)` — jamais une exception hors Streamlit."""
    try:
        return st.session_state.get(_CUSTOM_SINCE), st.session_state.get(_CUSTOM_UNTIL)
    except Exception:      # noqa: BLE001 — appelé depuis un test headless
        return None, None


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

    # LES DEUX DATES N'APPARAISSENT QUE SI ON LES A DEMANDÉES. Un sélecteur de dates
    # affiché en permanence à côté de six raccourcis, c'est deux façons de dire la même
    # chose sur la même ligne — et la plus lourde des deux occupe la place tout le
    # temps pour servir une fois.
    if chosen == "custom":
        col_a, col_b = st.columns(2)
        with col_a:
            st.date_input("Du", key=_CUSTOM_SINCE, format="DD/MM/YYYY")
        with col_b:
            st.date_input("Au", key=_CUSTOM_UNTIL, format="DD/MM/YYYY",
                          value=st.session_state.get(_CUSTOM_UNTIL) or _dt.date.today())
    return chosen
