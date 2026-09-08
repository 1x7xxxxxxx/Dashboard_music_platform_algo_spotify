"""Guard: le bandeau de mise en route est replié quand il n'a plus rien à demander.

Type: Test
Uses: streamlit.testing.v1.AppTest, live Postgres (spotify_etl)
Depends on: views/home._section_onboarding, utils.setup_completion
Persists in: —

Demandé le 2026-09-08 : « mets d'office la mise en route config terminée, bandeau non
déplié si la config est terminée et bandeau déplié si config non terminée ».

C'est la même information dans les deux cas ; ce qui change est ce qu'elle DEMANDE.
Tant qu'il reste une étape, le bandeau est la première chose à faire et il occupe la
place ; une fois terminé, il ne réclame plus rien et n'a pas à repousser les chiffres
vers le bas à chaque visite.

Le garde lit `expanded` sur le proto de l'élément, pas le code source : un
`st.expander(..., expanded=X)` peut être écrit correctement et rendu par une branche
qu'on n'atteint pas. Ce qui compte est ce que la page rend, pour un locataire dont
l'état de configuration a été MESURÉ, pas supposé.
"""
from __future__ import annotations

import os
import socket
import time

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

_BANNER_MARK = "Mise en route"


def _tenants_by_completion() -> tuple:
    """(un locataire configuré, un locataire non configuré) — mesurés, pas devinés."""
    from src.dashboard.utils import get_db_connection
    from src.dashboard.utils.setup_completion import read_setup_state

    db = get_db_connection()
    done = todo = None
    try:
        rows = db.fetch_query("SELECT id FROM saas_artists WHERE active ORDER BY id")
        for (aid,) in rows or []:
            state = read_setup_state(db, int(aid), None)
            if not state.steps:
                continue
            if state.complete and done is None:
                done = int(aid)
            if not state.complete and todo is None:
                todo = int(aid)
    finally:
        db.close()
    return done, todo


def _home(artist_id: int):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("src/dashboard/app.py", default_timeout=180)
    for key, value in {
        "authenticated": True, "role": "artist", "artist_id": artist_id,
        "username": "artist@test", "email": "artist@test", "name": "artist@test",
        "_last_activity": time.time(), "_nav_page": "home",
    }.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception, at.exception
    return at


def _banner(at):
    for element in at.get("expander"):
        label = getattr(element.proto, "label", "")
        if _BANNER_MARK in label:
            return element
    return None


def test_a_finished_setup_is_folded() -> None:
    done, _ = _tenants_by_completion()
    if done is None:
        pytest.skip("aucun locataire à la configuration terminée dans la base locale")
    banner = _banner(_home(done))
    assert banner is not None, (
        f"aucun bandeau « {_BANNER_MARK} » sur l'accueil — garde à repointer")
    assert banner.proto.expanded is False, (
        "le bandeau de mise en route est déplié alors que la configuration est "
        "terminée : il repousse les chiffres à chaque visite sans rien demander")
    assert "terminée" in banner.proto.label or "complete" in banner.proto.label.lower(), (
        f"le titre du bandeau replié ne porte pas le verdict : {banner.proto.label!r}. "
        "Replié, le titre est TOUT ce qu'on lit.")


def test_an_unfinished_setup_stays_open() -> None:
    _, todo = _tenants_by_completion()
    if todo is None:
        pytest.skip("aucun locataire à la configuration inachevée dans la base locale")
    banner = _banner(_home(todo))
    assert banner is not None, (
        f"aucun bandeau « {_BANNER_MARK} » sur l'accueil — garde à repointer")
    assert banner.proto.expanded is True, (
        "le bandeau est replié alors qu'il reste des étapes : la première chose à "
        "faire est cachée derrière un clic")
