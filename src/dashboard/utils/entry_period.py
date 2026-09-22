"""La période d'une SAISIE — des raccourcis, pas deux dates à taper.

Type: Utility
Uses: streamlit
Depends on: rien
Persists in: nothing (l'appelant écrit `period_start` / `period_end`)

Pourquoi un troisième module de période, et pourquoi ce n'en est pas un
-----------------------------------------------------------------------

Le dépôt porte DEUX vocabulaires de période, et c'est une décision argumentée —
**ADR-020** : celui de l'accueil est calendaire (« 30 jours », « depuis le début »),
celui des pages plateforme est ancré sur un évènement (« depuis la dernière
sortie »). Les unifier appauvrirait le second. Ce module n'en ajoute pas un
troisième : les deux autres répondent à *« quelle fenêtre je REGARDE »*, celui-ci
répond à *« sur quelle fenêtre cette valeur a été PRODUITE »*.

La différence est concrète. Un filtre de lecture peut se tromper sans conséquence —
on recadre et on relit. Une période de saisie devient une COLONNE en base
(`period_start`, `period_end` de `s4a_song_playlist_adds` et
`s4a_song_algo_outcomes`) : elle décrit ce que le chiffre saisi mesure, et une
erreur y est indiscernable d'une vraie donnée six mois plus tard.

Ce qu'il remplace, et pourquoi
------------------------------
Deux paires de `st.date_input("Début") / st.date_input("Fin")` dans
`views/saisie_s4a.py`, sans aucun raccourci. Demande du propriétaire le
2026-09-22 : « début fin avec des valeurs à rentrer c'est pas très agréable ».

Le fond dépasse le confort. Les fenêtres que Spotify for Artists sait afficher sont
**7 jours, 28 jours et 12 mois** — ce sont les seules bornes pour lesquelles un
chiffre existe à recopier. Une paire de dates libres invite à saisir « du 3 au 19 »,
période pour laquelle S4A n'affiche rien : le champ accepte alors une valeur que sa
source ne peut pas produire. Un raccourci qui nomme les fenêtres RÉELLES de l'outil
source est donc plus juste, pas seulement plus rapide.

⚠️ « Sur mesure » reste offert, et c'est délibéré : le cas des premiers jours d'une
sortie n'a pas de fenêtre S4A, on lit alors un graphique. Le retirer supprimerait un
usage réel pour faire respecter une règle qui ne vaut que par défaut.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Optional

import streamlit as st

# Les fenêtres que Spotify for Artists sait afficher, plus l'ancrage sur la sortie.
# L'ordre est celui dans lequel on les utilise, pas l'ordre croissant : la fenêtre
# de 28 jours est celle qui alimente le modèle, elle vient donc en premier.
PRESETS: dict[str, tuple[Optional[int], str]] = {
    "28d": (28, "28 jours"),
    "7d": (7, "7 jours"),
    "12m": (365, "12 mois"),
    "release": (None, "🚀 Depuis la sortie"),
    "custom": (None, "🎯 Sur mesure"),
}

DEFAULT = "28d"


@dataclass(frozen=True)
class EntryPeriod:
    """La fenêtre saisie, et le préréglage qui l'a produite."""

    start: _dt.date
    end: _dt.date
    preset: str

    @property
    def label(self) -> str:
        return PRESETS[self.preset][1]

    @property
    def days(self) -> int:
        return (self.end - self.start).days


def resolve(preset: str, today: _dt.date,
            release: Optional[_dt.date] = None,
            custom: Optional[tuple[_dt.date, _dt.date]] = None) -> EntryPeriod:
    """La fenêtre, sans Streamlit — c'est ce que les tests appellent.

    Séparé du rendu pour la même raison que `period_filter._resolve_window` : une
    règle de dates se vérifie sur des dates, pas sur un widget.
    """
    if preset == "custom" and custom:
        debut, fin = custom
        return EntryPeriod(debut, fin, "custom")
    if preset == "release":
        # Sans date de sortie connue, on ne devine pas : on retombe sur 28 jours
        # et l'appelant le DIT à l'écran. Inventer une borne de sortie écrirait
        # une période fausse dans une colonne que personne ne relira.
        if release is None:
            return EntryPeriod(today - _dt.timedelta(days=28), today, "28d")
        return EntryPeriod(release, today, "release")
    jours = PRESETS.get(preset, PRESETS[DEFAULT])[0] or 28
    return EntryPeriod(today - _dt.timedelta(days=jours), today, preset)


def entry_period_selector(*, key: str, release: Optional[_dt.date] = None,
                          today: Optional[_dt.date] = None) -> EntryPeriod:
    """Le sélecteur. Rend la fenêtre choisie, jamais `None`."""
    today = today or _dt.date.today()
    choix = st.segmented_control(
        "Période de la saisie", list(PRESETS),
        format_func=lambda k: PRESETS[k][1], default=DEFAULT,
        key=f"{key}_preset", label_visibility="collapsed",
    ) or DEFAULT

    custom = None
    if choix == "custom":
        rng = st.date_input(
            "Plage", value=(today - _dt.timedelta(days=7), today),
            format="DD/MM/YYYY", key=f"{key}_range", label_visibility="collapsed",
        )
        if isinstance(rng, tuple) and len(rng) == 2:
            custom = rng
        else:
            st.info("Sélectionne une date de fin.")
            st.stop()

    if choix == "release" and release is None:
        st.caption("Date de sortie inconnue pour ce titre — fenêtre de 28 jours utilisée.")

    fenetre = resolve(choix, today, release, custom)
    st.caption(f"Du **{fenetre.start:%d/%m/%Y}** au **{fenetre.end:%d/%m/%Y}** "
               f"· {fenetre.days} jours")
    return fenetre
