"""Un compte rendu d'action qui survit au rerun sans tuer les boutons qu'il porte.

Type: Utility
Uses: streamlit
Triggers: upload_csv.render_uploader, credentials/_render.render_save_verdict
Depends on: la clé de session `_nav_page` posée par app.py
Persists in: st.session_state

`st.rerun()` efface tout ce qui a été écrit avant lui, donc un compte rendu voyage
par la session. Jusqu'ici on le CONSOMMAIT au rendu (`session_state.pop`), pour qu'il
ne réapparaisse pas indéfiniment en contredisant l'état.

Ce `pop` est juste pour un message et faux dès que le bloc porte un bouton — c'est le
défaut signalé le 2026-09-08, « quand je clique sur configurer le mapping, ça me
renvoie nulle part ». Un clic ne se lit pas au moment du clic : il déclenche un rerun,
et `st.button(...)` ne rend `True` que si le widget est ré-instancié pendant ce rerun.
La valeur ayant été consommée au rendu précédent, le bloc est sauté, le bouton
n'existe pas, et le clic est jeté. Le bouton était mort sur les deux surfaces qui
terminent la mise en route.

D'où la borne posée ici : on garde la valeur, mais **le temps d'une page**. Elle
disparaît dès que l'artiste est ailleurs — donc jamais « des jours plus tard », ce qui
était la raison d'être du `pop`. Ni un état, ni un fantôme : le compte rendu de ce
qu'on vient de faire, visible tant qu'on est là où on l'a fait.
"""
from __future__ import annotations

import streamlit as st

_PAGE_SUFFIX = "__page"


def _current_page() -> str:
    return str(st.session_state.get("_nav_page", ""))


def pending_notice(key: str):
    """La valeur en attente sous `key`, tant qu'on est sur la page qui l'a vue naître.

    Rend `None` — et oublie la valeur — dès que la page courante n'est plus celle du
    premier rendu. Idempotente : appelée deux fois dans le même rendu, elle rend deux
    fois la même chose, ce dont dépend un bloc qui se dessine puis se relit.
    """
    if key not in st.session_state:
        return None
    born = st.session_state.get(key + _PAGE_SUFFIX)
    here = _current_page()
    if born is None:
        st.session_state[key + _PAGE_SUFFIX] = here
        return st.session_state[key]
    if born != here:
        clear_notice(key)
        return None
    return st.session_state[key]


def clear_notice(key: str) -> None:
    """Oublie le compte rendu et l'ancrage de page qui va avec.

    Appelée par le GESTE qui clôt le message — le bouton qui emmène ailleurs — et non
    par son affichage : c'est toute la différence avec le `pop` qu'elle remplace.
    """
    st.session_state.pop(key, None)
    st.session_state.pop(key + _PAGE_SUFFIX, None)
