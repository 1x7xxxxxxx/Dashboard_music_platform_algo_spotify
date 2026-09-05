"""La barre d'onglets montre ce qui est fait, et ouvre ce qui reste.

Type: Test
Uses: streamlit.testing.v1.AppTest, live Postgres
Depends on: views/credentials/router.py, _registry.py, meta_extra_accounts.py
Persists in: un locataire jetable

Demandé le 2026-09-05 : « en vert quand c'est configuré uniquement, et on ne doit pas
automatiquement arriver sur l'onglet vert — ça passe à celui directement à droite ».

Depuis que les liens d'inscription se matérialisent seuls, un artiste arrive ici avec
Spotify déjà branché sans avoir rien saisi sur cette page. L'ouvrir lui montre un
formulaire qu'il vient de remplir ailleurs.
"""
import json
import os
import socket
import uuid

import pytest

_DB_HOST, _DB_PORT = "127.0.0.1", 5433


def _db():
    if not os.environ.get("DATABASE_URL"):
        try:
            with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
                pass
        except OSError:
            return None
    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        db.fetch_query("SELECT 1 FROM saas_artists LIMIT 1")
        return db
    except Exception:  # noqa: BLE001
        return None


pytestmark = pytest.mark.skipif(_db() is None, reason="needs the provisioned DB")


@pytest.fixture()
def tenant_with(request):
    """Un locataire jetable portant exactement les plateformes demandées."""
    db = _db()
    slug = f"e2e-tabs-{uuid.uuid4().hex[:8]}"
    aid = db.fetch_query(
        "INSERT INTO saas_artists (name, slug, tier, active) "
        "VALUES (%s, %s, 'free', TRUE) RETURNING id", (f"E2E {slug}", slug))[0][0]
    for platform, extra in getattr(request, "param", {}).items():
        db.execute_query(
            "INSERT INTO artist_credentials (artist_id, platform, extra_config) "
            "VALUES (%s, %s, %s)", (aid, platform, json.dumps(extra)))
    yield db, aid
    db.execute_query("DELETE FROM artist_credentials WHERE artist_id = %s", (aid,))
    db.execute_query("DELETE FROM saas_artists WHERE id = %s", (aid,))


def _render(artist_id: int):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(f"""
import sys
sys.path.insert(0, {os.getcwd()!r})
import streamlit as st
st.session_state["role"] = "artist"
st.session_state["artist_id"] = {artist_id}
st.session_state["email"] = "a@t"
st.session_state["name"] = "a@t"
st.session_state["authenticated"] = True
from src.dashboard.views.credentials import show
show()
""")
    at.run(timeout=200)
    assert not at.exception, at.exception

    def flat(node, out=None):
        out = [] if out is None else out
        kids = getattr(node, "children", None)
        for child in (kids.values() if isinstance(kids, dict) else (kids or [])):
            out.append(child)
            flat(child, out)
        return out

    bars = [e for e in flat(at.main) if type(e).__name__ == "ButtonGroup"]
    assert bars, "la barre d'onglets a disparu"
    return bars[0]


@pytest.mark.parametrize("tenant_with", [
    {"spotify": {"spotify_artist_id": "4qG1qjeHfkASTdyRGbLWbV"}},
], indirect=True)
def test_a_configured_platform_is_green_and_is_not_the_landing_tab(tenant_with):
    """Le cas exact de la demande : Spotify configuré ⇒ on ouvre SoundCloud."""
    _db_, aid = tenant_with
    bar = _render(aid)

    assert "🟢" in str(bar), "l'onglet configuré n'est pas en vert"
    assert bar.value != "spotify", (
        "la page s'ouvre sur l'onglet DÉJÀ configuré : l'artiste y voit un "
        "formulaire qu'il vient de remplir ailleurs")
    assert bar.value == "soundcloud", (
        f"on n'ouvre pas l'onglet suivant mais {bar.value!r}")


@pytest.mark.parametrize("tenant_with", [{}], indirect=True)
def test_with_nothing_configured_the_first_tab_opens_and_nothing_is_green(tenant_with):
    """Le vert doit distinguer : partout, il ne distingue rien."""
    _db_, aid = tenant_with
    bar = _render(aid)

    assert "🟢" not in str(bar), "un onglet est vert alors que rien n'est configuré"
    assert bar.value == "spotify", (
        f"le premier onglet n'est plus celui qui s'ouvre ({bar.value!r})")


def test_the_agency_field_left_credentials_for_the_meta_ads_page():
    """« Ça ne doit pas être dans l'onglet credential. »

    Credentials répond à « comment te connecter » ; un compte d'agence est une
    déclaration de périmètre. Même mouvement que les titres SoundCloud hébergés
    ailleurs, partis sur leur page de performance le 2026-09-04.
    """
    import ast
    from pathlib import Path

    from src.dashboard.views.credentials._registry import PLATFORMS

    keys = [f["key"] for f in PLATFORMS["meta"]["fields"]]
    assert "extra_account_ids" not in keys, (
        "le champ d'agence est revenu dans l'onglet Credentials")

    # Et il est bien RENDU ailleurs — sinon on l'a simplement perdu.
    src = (Path(__file__).resolve().parents[1]
           / "src/dashboard/views/meta_ads_overview.py").read_text(encoding="utf-8")
    called = {getattr(n.func, "id", "") or getattr(n.func, "attr", "")
              for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call)}
    assert "render_extra_ad_accounts" in called, (
        "le champ a quitté Credentials sans arriver sur la page Meta Ads")


@pytest.mark.parametrize("tenant_with", [
    {"meta": {"account_id": "act_111",
              "account_ids": ["act_111", "act_222"],
              "ig_user_id": "17841400000000000"}},
], indirect=True)
def test_saving_credentials_never_erases_the_agency_accounts(tenant_with):
    """Le déplacement d'un champ ne doit pas devenir une suppression de données.

    Les comptes supplémentaires ne se saisissent plus dans Credentials, mais ils
    vivent dans la MÊME ligne. Sans relecture, `with_meta_accounts` reconstruirait la
    liste depuis le seul champ principal et les effacerait à chaque enregistrement.
    """
    from src.dashboard.views.credentials._render import _saved_meta_accounts

    db, aid = tenant_with
    assert _saved_meta_accounts(db, aid) == ["act_111", "act_222"], (
        "les comptes déjà enregistrés ne sont plus relus")

    # Et le BRANCHEMENT, pas seulement la fonction. Sans cette moitié, le test reste
    # vert quand `_handle_save` cesse d'injecter la liste relue dans les comptes à
    # écrire — c'est-à-dire au moment précis où les données seraient effacées. Trois
    # gardes ont eu ce trou aujourd'hui ; celui-ci le ferme d'emblée.
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1]
           / "src/dashboard/views/credentials/_render.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "_handle_save")
    called = {getattr(n.func, "id", "") for n in ast.walk(fn) if isinstance(n, ast.Call)}
    assert "_saved_meta_accounts" in called, (
        "`_handle_save` ne relit plus les comptes enregistrés : réenregistrer les "
        "credentials effacerait les comptes d'agence")
    # La liste relue doit ENTRER dans la construction, pas rester en variable morte.
    starred = [n for n in ast.walk(fn) if isinstance(n, ast.Starred)
               and getattr(n.value, "id", "") == "_kept"]
    assert starred, (
        "la liste relue n'est plus dépliée dans les comptes à écrire — elle est "
        "calculée puis jetée")
