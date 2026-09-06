"""Guard: a view that renders nothing must SAY why — silence is the third failure.

Type: Utility
Uses: streamlit.testing.v1.AppTest, live Postgres
Triggers: pytest
Persists in: nothing

Error class `view-renders-nothing-and-says-nothing`.

Le render-smoke voisin demande « la vue lève-t-elle ? ». C'est la première des trois
façons dont une fonctionnalité cesse de servir, et la seule qui alerte toute seule :

  1. elle plante            → exception, frontière centrale, e-mail. COUVERT.
  2. elle refuse en silence → `check_csv_rejections`, depuis le 2026-09-06. COUVERT.
  3. elle s'affiche VIDE    → aucune exception, aucun log, un écran blanc. ICI.

Un graphique dont la requête ne rend plus rien, une page dont la table a été renommée,
un onglet dont la donnée est partie : tout cela rend « correctement » et ne dit rien.
Demandé le 2026-09-06 : « de l'alerting … pour des fonctionnalités qui ne
fonctionneraient pas comme les graphiques ».

CE QUI EST EXIGÉ, et pourquoi c'est atteignable. Une vue doit émettre au moins UN
élément substantiel — un graphique, un tableau, une métrique — OU un message explicite
qui nomme l'absence (`st.info`, `st.warning`, `st.error`). La seconde branche est la
convention du dépôt : dire l'absence plutôt que la laisser deviner. Ce qui est interdit
est le troisième cas : un titre, et rien.
"""
from __future__ import annotations

import os
import socket

import pytest

_DB_HOST, _DB_PORT = "127.0.0.1", 5433


def _db_ready() -> bool:
    if os.environ.get("DATABASE_URL"):
        return True
    try:
        with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="needs the provisioned DB")

# Les vues qu'un artiste atteint et qui doivent MONTRER quelque chose. La liste est
# volontairement celle du parcours — pas toutes les vues : les pages d'action
# (formulaires) sont couvertes par leurs propres gardes.
_VIEWS = [
    "home", "spotify_s4a_combined", "apple_music", "youtube", "soundcloud",
    "instagram", "meta_ads_overview", "revenue_forecast", "imusician",
    "onboarding_health", "data_wrapped",
]

_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["role"] = "admin"
st.session_state["artist_id"] = 1
st.session_state["email"] = "admin@test"
st.session_state["authenticated"] = True
from src.dashboard.views.{view} import show
show()
"""


@pytest.mark.parametrize("view", _VIEWS)
def test_a_view_shows_data_or_names_its_absence(view):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_SCRIPT.format(root=os.getcwd(), view=view))
    at.run(timeout=240)
    assert not at.exception, f"{view} a levé : {at.exception}"

    # Ce qui compte comme « montrer » : une donnée rendue, sous n'importe quelle forme.
    substantive = 0
    for kind in ("dataframe", "table", "metric", "line_chart", "bar_chart",
                 "area_chart", "plotly_chart", "altair_chart", "pyplot",
                 "map", "json", "code"):
        try:
            substantive += len(at.get(kind))
        except Exception:      # noqa: BLE001 — l'élément n'existe pas dans cette version
            pass

    # Ce qui compte comme « dire pourquoi » : un message adressé au lecteur.
    spoken = len(at.info) + len(at.warning) + len(at.error) + len(at.success)

    assert substantive or spoken, (
        f"« {view} » n'affiche NI donnée NI explication — un titre, et rien.\\n"
        "C'est la troisième façon de ne plus fonctionner : elle ne lève pas, donc "
        "aucune alerte ne la voit, et l'artiste regarde un écran vide sans savoir "
        "s'il doit attendre, configurer, ou signaler.\\n"
        "Deux sorties acceptables : rendre la donnée, ou nommer son absence avec "
        "`st.info` / `st.warning`.")
