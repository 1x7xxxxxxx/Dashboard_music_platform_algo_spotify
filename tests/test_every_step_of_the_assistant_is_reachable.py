"""Guard: chaque étape de l'assistant a un chemin qui y mène.

Type: Test
Uses: streamlit.testing.v1.AppTest, live Postgres (spotify_etl)
Depends on: src/dashboard/app.py rendu ENTIER (barre latérale + vue)
Persists in: —

Error class `a-step-that-nothing-routes-to`.

L'assistant a deux étapes — « 1. Bienvenue & choix » et « 2. Où tu en es ». Sur un
compte **déjà configuré**, la seconde n'était atteignable par aucun chemin :

* `sync_step_on_arrival()` remet à l'étape 1 dès qu'on arrive d'une autre page ;
* le seul bouton qui pose l'étape 2 — « 🔑 Connecter mes sources → » — quitte
  l'assistant dans la même action ;
* et les deux boutons de la barre latérale qui y mènent n'étaient rendus que sous
  `_bare`, c'est-à-dire uniquement en mode première connexion.

Signalé le 2026-09-08 : « quand je clique sur mise en route (assistant), je n'arrive
pas sur la page d'onboarding, j'ai uniquement les 2 onglets bienvenue / offre ».

Pourquoi aucun test existant ne pouvait le voir : `test_views_render_smoke` appelle
`onboarding.show()` **sans barre latérale**, et c'est la barre qui porte les boutons
d'étape. La vue et sa navigation ne coexistent dans aucun autre test de ce dépôt.
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


def _configured_tenant() -> int:
    """Un locataire dont la mise en route est FINIE — le cas du défaut.

    Sur un compte neuf le mode première connexion masquait le défaut : les boutons
    étaient rendus. Prendre n'importe quel locataire ne prouverait donc rien.
    """
    from src.dashboard.utils import get_db_connection
    db = get_db_connection()
    try:
        rows = db.fetch_query(
            "SELECT a.id FROM saas_artists a "
            " WHERE a.active AND EXISTS (SELECT 1 FROM artist_credentials c "
            "                             WHERE c.artist_id = a.id) "
            " ORDER BY a.id LIMIT 1")
    finally:
        db.close()
    if not rows:
        pytest.skip("aucun locataire configuré dans la base locale")
    return int(rows[0][0])


def _render_assistant(artist_id: int):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(_APP, default_timeout=180)
    for key, value in {
        "authenticated": True, "role": "artist", "artist_id": artist_id,
        "username": "artist@test", "email": "artist@test", "name": "artist@test",
        "_last_activity": time.time(), "_nav_page": "onboarding",
    }.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception, at.exception
    return at


def test_the_second_step_is_reachable_on_a_configured_account() -> None:
    """Le bouton qui mène à « 2. Où tu en es » doit exister, hors première connexion."""
    at = _render_assistant(_configured_tenant())
    jumps = [b for b in at.button if str(b.key or "").startswith("_onb_jump_")]
    assert jumps, (
        "aucun bouton d'étape n'est rendu : l'assistant s'ouvre sur l'étape 1 et rien "
        "ne mène à l'étape 2 (classe `a-step-that-nothing-routes-to`)")
    assert any("_onb_jump_2" == b.key for b in jumps), (
        f"les étapes rendues sont {[b.key for b in jumps]} — l'étape 2 n'en est pas")


def test_clicking_the_step_button_actually_changes_the_step() -> None:
    """Rendu ne vaut pas atteignable : on clique, et on regarde l'étape."""
    at = _render_assistant(_configured_tenant())
    target = [b for b in at.button if b.key == "_onb_jump_2"]
    if not target:
        pytest.fail("l'étape 2 n'a pas de bouton — voir le test précédent")
    after = target[0].click().run()
    assert not after.exception, after.exception
    assert after.session_state["_onboarding_step"] == 2, (
        "le clic n'a pas changé d'étape : le bouton est rendu mais inopérant")
