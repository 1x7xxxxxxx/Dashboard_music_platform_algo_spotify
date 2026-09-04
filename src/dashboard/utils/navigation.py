"""Aller à une page depuis n'importe où, sans rechargement du navigateur.

Type: Utility
Uses: streamlit
Triggers: un bouton d'étape, une carte, un lien d'onboarding
Depends on: les clés de session `_nav_page` / `_nav_<section>` posées par app.py
Persists in: st.session_state

Pourquoi un module plutôt qu'une fonction locale : `onboarding.py` portait déjà son
`_goto()`, et l'accueil en avait besoin. Recopier la règle de navigation dans une
deuxième vue, c'est la laisser diverger — le dépôt a déjà payé ça ailleurs (registres
recopiés, ordres de plateformes en triple). Une seule fonction, deux appelants.

Ce que la navigation exige, et qui n'est pas évident :

* poser `_nav_page` SUFFIT depuis le 2026-09-04, et c'est le seul point délicat de ce
  module. Cette fonction remettait elle-même chaque radio de section à `None` — et elle
  est appelée depuis une VUE, donc après que la barre latérale a instancié ces radios.
  Streamlit l'interdit : « `st.session_state._nav_reports` cannot be modified after the
  widget with key `_nav_reports` is instantiated ». Tout bouton de navigation depuis une
  vue plantait donc la page, y compris les quatre étapes de l'accueil. Sur l'assistant,
  le défaut était masqué par une route anticipée `?page=onboarding` qui ne rendait
  aucune barre latérale — supprimée le même jour, ce qui l'a rendu visible.
  `app.resolve_nav_page` fait désormais accorder le menu et la page à CHAQUE rendu,
  avant instanciation, et c'est le seul endroit qui touche ces clés ;
* les widgets ne se modifient pas après instanciation, mais `_nav_page` n'en est pas
  un : l'écrire ici puis `st.rerun()` est légal, et c'est tout ce qu'il faut ;
* le paramètre d'URL `?page=` doit partir, sinon `main()` ré-épingle la page profonde
  (l'onboarding) à chaque rerun.
"""
from __future__ import annotations

import streamlit as st

_PAGE_KEY = "_nav_page"


def goto(page_key: str) -> None:
    """Navigue vers `page_key` et relance le script. Ne revient jamais."""
    st.session_state[_PAGE_KEY] = page_key

    # Aucune écriture sur les radios de section ici — voir la docstring. Elles sont déjà
    # instanciées quand une vue appelle `goto`, et `app.resolve_nav_page` les accorde à
    # la page au début du rendu suivant.

    # `?page=onboarding` est épinglé par main() avant que le menu ne tourne : le laisser
    # ferait revenir sur l'onboarding au rerun suivant.
    try:
        del st.query_params["page"]
    except Exception:      # noqa: BLE001 — absent, ce qui est le cas nominal
        pass

    st.rerun()
