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

* poser `_nav_page` ne suffit pas — les radios de section de la barre latérale gardent
  leur sélection, et l'artiste voit la page changer pendant que le menu montre encore
  l'ancienne entrée. Il faut les remettre à `None`, ce que `app._on_nav_select` fait
  déjà pour un clic dans le menu ;
* les widgets ne se modifient pas après instanciation, mais `app.show_navigation_menu`
  répare l'état AVANT de les créer : écrire ici puis `st.rerun()` est donc légal ;
* le paramètre d'URL `?page=` doit partir, sinon `main()` ré-épingle la page profonde
  (l'onboarding) à chaque rerun.
"""
from __future__ import annotations

import streamlit as st

_PAGE_KEY = "_nav_page"
# Clés de session qui portent l'état du menu et NE sont pas des radios de section.
_NOT_A_SECTION = {_PAGE_KEY, "_nav_start"}


def goto(page_key: str) -> None:
    """Navigue vers `page_key` et relance le script. Ne revient jamais."""
    st.session_state[_PAGE_KEY] = page_key

    # Désélectionner toutes les radios de section : sans ça, le menu resterait sur
    # l'entrée précédente pendant que le contenu a changé.
    for key in [k for k in st.session_state
                if k.startswith("_nav_") and k not in _NOT_A_SECTION]:
        st.session_state[key] = None

    # `?page=onboarding` est épinglé par main() avant que le menu ne tourne : le laisser
    # ferait revenir sur l'onboarding au rerun suivant.
    try:
        del st.query_params["page"]
    except Exception:      # noqa: BLE001 — absent, ce qui est le cas nominal
        pass

    st.rerun()
