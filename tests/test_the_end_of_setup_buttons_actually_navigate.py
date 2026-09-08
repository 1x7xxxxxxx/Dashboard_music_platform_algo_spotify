"""Guard: les boutons qui terminent la mise en route emmènent vraiment ailleurs.

Type: Test
Uses: streamlit.testing.v1.AppTest, live Postgres (spotify_etl)
Depends on: upload_csv.render_uploader, credentials/_render.render_save_verdict
Persists in: —

Ce fichier existe parce qu'aucun autre ne pouvait voir le défaut du 2026-09-08.

`test_views_render_smoke.py` appelle chaque `show()` **une fois** : il prouve que le
bouton est dessiné, ce qu'il était. Le défaut n'était pas dans le rendu, il était dans
le rendu SUIVANT — le compte rendu qui porte le bouton était consommé (`pop`) à
l'affichage, donc au rerun déclenché par le clic le bloc n'existait plus, le widget
n'était pas ré-instancié, et le geste était jeté. « Quand je clique sur configurer le
mapping, ça me renvoie nulle part. »

On va donc jusqu'au bout du geste : rendre, **cliquer**, puis regarder où l'on est.

Pourquoi la fonction et non `app.py` entier
-------------------------------------------
Rendre l'application entière serait mieux — c'est ce qui manque à ce dépôt, et la
barre latérale et la vue ne coexistent dans aucun test. Ce n'est pas possible ICI, et
la raison n'est pas dans notre code : la barre d'onglets de Credentials est un
`st.segmented_control`, et le harnais AppTest reconstruit son état en itérant sa
valeur — une CHAÎNE — caractère par caractère, puis échoue sur `KeyError: '_'`
(`element_tree.py:744`, `indices`). Tout second `.run()` sur cette page meurt là,
avant d'atteindre notre code. On rend donc la fonction qui porte le bouton, sans la
barre d'onglets : le clic, lui, est réel.
"""
from __future__ import annotations

import os
import socket

import pytest

_DB_HOST, _DB_PORT = "127.0.0.1", 5433


def _db_ready() -> bool:
    if not os.environ.get("DATABASE_URL"):
        try:
            with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
                pass
        except OSError:
            return False
    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        if db is None:
            return False
        try:
            db.fetch_query("SELECT 1 FROM saas_artists LIMIT 1")
            return True
        finally:
            db.close()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason=f"No provisioned Postgres on {_DB_HOST}:{_DB_PORT} — needs the live DB",
)

_SESSION = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state.setdefault("authenticated", True)
st.session_state.setdefault("role", "artist")
st.session_state.setdefault("artist_id", 1)
st.session_state.setdefault("email", "artist@test")
st.session_state.setdefault("_nav_page", "credentials")
"""

# Le compte rendu N'EST PAS semé par le script, et c'est le point qui décide si ce
# fichier prouve quoi que ce soit. Un `setdefault` en tête de script le remettrait à
# CHAQUE exécution, y compris celle du clic — le `pop` fautif serait alors compensé
# par le harnais, et les deux tests restaient verts sur le défaut. Mesuré : c'est ce
# qu'ils faisaient à leur première écriture, le 2026-09-08. Il est donc posé UNE
# fois, sur la session, avant le premier rendu — comme la vraie vie le pose.
_CSV_SCRIPT = _SESSION + """
from src.dashboard.views.upload_csv import render_uploader
from src.dashboard.utils import get_db_connection
render_uploader(get_db_connection(), 1)
"""

_VERDICT_SCRIPT = _SESSION + """
from src.dashboard.views.credentials._render import render_save_verdict
render_save_verdict(next_platform=None, selection_complete=True)
"""


def _run(script: str, seed: dict):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(script.format(root=os.getcwd()), default_timeout=120)
    for key, value in seed.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception, at.exception
    return at


def _click(at, predicate, what: str):
    hits = [b for b in at.button if predicate(b)]
    assert hits, (
        f"{what} n'est pas rendu — le test ne prouve plus rien, garde à repointer."
    )
    after = hits[0].click().run()
    assert not after.exception, after.exception
    return after


def test_the_csv_mapping_cta_reaches_the_mapping_page():
    """Le geste qui suit un import : « 🔗 Confirmer le nom des titres »."""
    from src.dashboard.views.upload_csv import _last_result_key
    seed = {_last_result_key(1): {"rows": [], "n_ok": 1, "n_err": 0,
                                  "total_rows": 42, "notes": []}}
    at = _click(_run(_CSV_SCRIPT, seed),
                lambda b: b.key == "_csv_to_mapping_1",
                "le bouton de mapping")
    assert at.session_state["_nav_page"] == "meta_mapping", (
        "le bouton de mapping n'a mené nulle part : le clic a été jeté parce que le "
        "bloc qui le porte n'existait plus au rerun — classe "
        "`consumed-state-hides-its-own-widget`."
    )


def test_the_verdict_home_button_reaches_the_dashboard():
    """Le geste qui termine la mise en route : « 🏠 Aller au dashboard → ».

    Même forme, même défaut, même jour — et c'est la dernière chose qu'un artiste
    fait avant d'entrer dans l'application.
    """
    from src.dashboard.views.credentials._render import VERDICT_KEY
    at = _click(_run(_VERDICT_SCRIPT, {VERDICT_KEY: ("spotify", True, "")}),
                lambda b: str(b.key or "").startswith("_verdict_home_"),
                "le bouton d'entrée dans l'application")
    assert at.session_state["_nav_page"] == "home", (
        "le bouton d'entrée dans l'application n'a mené nulle part : même classe "
        "`consumed-state-hides-its-own-widget`."
    )
