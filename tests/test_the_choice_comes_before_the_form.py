"""Ce que la page montre EN PREMIER, et ce que la barre latérale ne dit plus.

Type: Test
Uses: streamlit.testing.v1.AppTest, live Postgres (spotify_etl)
Depends on: views/credentials/router.py, views/credentials/_render.py, app.py, auth.py
Persists in: —

Quatre demandes du 2026-09-05, toutes vérifiées SUR LE RENDU. Aucune ne se prouve en
lisant le code : un `st.container()` réservé au bon endroit reste vide si ce qu'on y
écrit appelle `st.sidebar.caption()`, qui ignore le `with` — c'est exactement ce qui
s'est passé au premier essai, et seul l'arbre rendu l'a montré.

1. La barre de plateformes est la PREMIÈRE ligne de la page. « On arrive directement
   sur *Saisir tes identifiants* mais on ne sait pas sur quelle plateforme. »
2. Plus aucune règle horizontale sur cette page. « Ça rajoute des trucs pour rien. »
3. L'en-tête de saisie NOMME sa plateforme.
4. La ligne « 🟢 n en ligne · 👥 n artistes » est au-dessus du logo, et
   « 🎤 Artiste — <adresse> » a disparu pour un artiste.

Le harnais render-smoke appelle chaque `show()` isolément et ne rend JAMAIS la barre
avec la vue : deux causes racines de navigation ont traversé 3755 tests verts pour
cette raison. Ici `_main_body()` est rendu en entier.
"""
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
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(
    not _db_ready(), reason=f"needs the provisioned DB on {_DB_HOST}:{_DB_PORT}")

_VIEW_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["role"] = "artist"
st.session_state["artist_id"] = {aid}
st.session_state["email"] = "a@t"
st.session_state["name"] = "a@t"
st.session_state["authenticated"] = True
from src.dashboard.views.credentials import show
show()
"""

_APP_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
sys.path.insert(0, {root!r} + "/src/dashboard")
import streamlit as st
st.session_state["role"] = {role!r}
st.session_state["artist_id"] = {aid}
st.session_state["email"] = "someone@example.test"
st.session_state["name"] = "someone@example.test"
st.session_state["authenticated"] = True
st.session_state["_nav_page"] = "credentials"
from src.dashboard.app import _main_body
_main_body()
"""


def _run(script: str, **kw):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(script.format(root=os.getcwd(), **kw))
    at.run(timeout=240)
    assert not at.exception, at.exception
    return at


def _flat(node):
    """Les éléments dans l'ordre du RENDU, conteneurs traversés.

    Itérer `at.main` / `at.sidebar` donne l'ordre des APPELS, pas celui de l'écran :
    un `st.container()` réservé tôt et rempli tard y sort à sa place d'appel. C'est
    précisément ce qu'on vérifie ici, donc on descend l'arbre. `children` est un
    dict indexé sur ces nœuds.
    """
    out = []
    kids = getattr(node, "children", None)
    for child in (kids.values() if isinstance(kids, dict) else (kids or [])):
        out.append(child)
        out.extend(_flat(child))
    return out


@pytest.fixture(scope="module")
def creds_page():
    return _run(_VIEW_SCRIPT, aid=18)


def test_the_platform_buttons_are_the_first_line_of_the_page(creds_page):
    kinds = [type(e).__name__ for e in _flat(creds_page.main)]
    assert "ButtonGroup" in kinds, "la barre de plateformes a disparu de la page"
    first_choice = kinds.index("ButtonGroup")
    # Rien d'autre qu'un bloc de structure et le titre avant elle : ni règle, ni
    # bandeau, ni formulaire. Ce que l'artiste voit d'abord est le CHOIX.
    before = [k for k in kinds[:first_choice]
              if k not in ("SpecialBlock", "Block", "Title")]
    assert not before, f"des éléments précèdent le choix de plateforme : {before}"


def test_the_page_carries_no_horizontal_rule(creds_page):
    rules = [e for e in _flat(creds_page.main)
             if type(e).__name__ == "Markdown"
             and str(getattr(e, "value", "")).strip() == "---"]
    assert not rules, f"{len(rules)} règle(s) horizontale(s) subsistent sur la page"


def test_the_entry_header_names_the_platform_it_configures(creds_page):
    headers = [str(e.value) for e in _flat(creds_page.main)
               if type(e).__name__ == "Markdown"
               and "orange-background" in str(getattr(e, "value", ""))]
    assert headers, "l'en-tête de saisie a disparu"
    assert any("Spotify" in h for h in headers), (
        f"l'en-tête ne nomme pas sa plateforme : {headers}")


def test_the_live_line_sits_above_the_logo():
    at = _run(_APP_SCRIPT, role="artist", aid=18)
    seq = []
    for e in _flat(at.sidebar):
        text = str(getattr(e, "value", "") or getattr(e, "body", "") or "")
        if "en ligne" in text and "artistes" in text:
            seq.append("live")
        elif "<img" in text:
            seq.append("logo")
    assert "live" in seq, "la ligne « n en ligne · n artistes » n'est pas rendue"
    assert "logo" in seq, "le logo n'est pas rendu"
    assert seq.index("live") < seq.index("logo"), (
        f"la ligne est SOUS le logo : {seq}")


def test_an_artist_is_not_told_their_own_address():
    at = _run(_APP_SCRIPT, role="artist", aid=18)
    texts = [str(getattr(e, "value", "") or getattr(e, "body", "") or "")
             for e in _flat(at.sidebar)]
    assert not any("someone@example.test" in x for x in texts), (
        "la barre latérale répète l'adresse de l'artiste")
    assert not any("🎤" in x and "—" in x for x in texts)


def test_an_admin_still_sees_which_identity_is_loaded():
    """Chez l'admin la ligne dit le locataire CHARGÉ, pas lui — elle reste."""
    at = _run(_APP_SCRIPT, role="admin", aid=1)
    texts = [str(getattr(e, "value", "") or getattr(e, "body", "") or "")
             for e in _flat(at.sidebar)]
    assert any("👑" in x for x in texts), "l'admin ne voit plus quelle identité est chargée"
