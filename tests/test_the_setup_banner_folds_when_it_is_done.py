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

from pathlib import Path

import pytest

# CHEMIN ABSOLU, dérivé de la racine du dépôt.
#
# `AppTest.from_file` résout un chemin RELATIF depuis le fichier qui l'appelle — donc
# depuis `tests/`, ce qui donne `tests/src/dashboard/app.py`. Le chemin relatif ne
# marchait que par la grâce de la version de Streamlit installée localement ; en CI il
# a rendu `FileNotFoundError` sur trois tests, et le rouge cachait tout ce qui suivait.
_APP = str(Path(__file__).resolve().parent.parent / "src" / "dashboard" / "app.py")

_DB_HOST, _DB_PORT = "127.0.0.1", 5433


# La porte LÉGÈRE. Le corps recopié ici importait `get_db_connection`
# (**5,30 s**, dont 5,19 s de Streamlit) et ouvrait une connexion À L'IMPORT du
# module, donc à la collecte, une fois par fichier et par worker.
# `tests.db_gate.db_ready` répond en 0,19 s, derrière un `lru_cache` partagé, et
# sonde en plus `DATABASE_URL` et le schéma réel. Le nom est conservé : seuls le
# coût et le nombre de connexions changent.
from tests.db_gate import db_ready as _db_ready  # noqa: E402


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

    at = AppTest.from_file(_APP, default_timeout=180)
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
