"""Choisir l'anglais une fois doit suffire.

Type: Test
Uses: ast, live Postgres
Depends on: src/dashboard/utils/lang_pref.py, i18n.py, auth.py, migrations/079
Persists in: nothing (le locataire d'essai est supprimé)

Demandé après le test artiste du 2026-08-30 : « on doit stocker quelque part si on
appuie sur le bouton anglais, ça le mémorise et ça propose automatiquement pour
l'artiste en question la langue, par défaut : français ».

Avant, le choix vivait dans `st.session_state['lang']` recopié dans `?lang=`. Ce
couple existe pour une raison qui n'a pas disparu — le login appelle
`session_state.clear()` (fixation de session MEDIUM-01), donc un choix fait AVANT
connexion serait effacé sans l'URL. Il survivait à la connexion, pas à la fermeture
de l'onglet ni au changement d'appareil.

`NULL` n'est pas `'fr'` : NULL veut dire « n'a jamais choisi ». La distinction
permettra de changer le défaut un jour sans écraser une décision explicite, et c'est
pour ça qu'aucune valeur n'est rétro-remplie sur les comptes existants — supposer
qu'ils ont « choisi » le français serait inventer une décision qu'ils n'ont pas prise.
"""
from __future__ import annotations

import ast
import os
import socket
import uuid
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
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
            db.fetch_query("SELECT lang FROM saas_users LIMIT 1")
            return True
        finally:
            db.close()
    except Exception:
        return False


def test_the_column_exists_and_the_migration_is_idempotent():
    """Sans la colonne, tout le reste échouerait pour une raison trompeuse."""
    sql = (_ROOT / "migrations" / "079_remember_the_artists_language.sql").read_text(
        encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS lang" in sql, (
        "la migration 079 n'ajoute plus `lang`, ou n'est plus idempotente — "
        "`tools/migrate.sh` rejoue tout le répertoire.")
    assert "DEFAULT" not in sql.split("ADD COLUMN")[1].split(";")[0], (
        "un DEFAULT sur `lang` effacerait la distinction entre « jamais choisi » "
        "(NULL) et « a choisi le français ».")


@pytest.mark.skipif(not _db_ready(),
                    reason=f"pas de Postgres provisionné sur {_DB_HOST}:{_DB_PORT} "
                           "— la persistance ne se vérifie que contre une vraie base")
def test_the_choice_survives_the_session_being_cleared():
    """Le cœur : `session_state.clear()` est ce que fait la connexion."""
    import streamlit as st

    from src.dashboard.utils import get_db_connection
    from src.dashboard.utils.lang_pref import load_preferred_lang, remember_lang

    tag = uuid.uuid4().hex[:8]
    db = get_db_connection()
    artist_id = db.fetch_query(
        "INSERT INTO saas_artists (name, slug, tier, active) "
        "VALUES (%s, %s, 'free', TRUE) RETURNING id",
        (f"Lang {tag}", f"lang-{tag}"))[0][0]
    user_id = db.fetch_query(
        "INSERT INTO saas_users (username, email, password_hash, role, artist_id, "
        "                        active, email_verified) "
        "VALUES (%s, %s, '!x', 'artist', %s, TRUE, TRUE) RETURNING id",
        (f"lang_{tag}", f"lang+{tag}@example.invalid", artist_id))[0][0]
    db.close()

    try:
        assert load_preferred_lang(user_id) is None, (
            "un compte neuf doit valoir NULL — pas 'fr'. La distinction est ce qui "
            "permettra de changer le défaut sans écraser un choix explicite.")

        st.session_state["user_id"] = user_id
        remember_lang("en")
        assert load_preferred_lang(user_id) == "en"

        st.session_state.clear()          # exactement ce que fait la connexion
        assert load_preferred_lang(user_id) == "en", (
            "le choix n'a pas survécu à session_state.clear() — c'est précisément le "
            "moment où l'ancien mécanisme le perdait.")

        st.session_state["user_id"] = user_id
        remember_lang("fr")
        assert load_preferred_lang(user_id) == "fr", "le retour au français ne prend pas"

        remember_lang("de")               # langue non gérée
        assert load_preferred_lang(user_id) == "fr", (
            "une langue inconnue a écrasé un choix valide")

        assert load_preferred_lang(None) is None, (
            "un visiteur anonyme n'a pas de ligne — la lecture doit rendre None, "
            "pas lever")
    finally:
        db = get_db_connection()
        db.execute_query("DELETE FROM saas_users WHERE id = %s", (user_id,))
        db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))
        db.close()


def test_i18n_does_not_depend_on_the_database_at_import():
    """`i18n` sert des surfaces sans base : PDF headless, DAGs, tests.

    C'est la raison d'être du module séparé. Un import de `project_db` au chargement
    de `i18n` casserait exactement les appelants qui n'ont pas de connexion — et le
    ferait au moment le plus difficile à diagnostiquer.
    """
    tree = ast.parse((_ROOT / "src/dashboard/utils/i18n.py").read_text(encoding="utf-8"))
    top_level = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = " ".join(ast.dump(n) for n in top_level)
    for forbidden in ("lang_pref", "project_db", "postgres_handler"):
        assert forbidden not in names, (
            f"i18n.py importe {forbidden} au niveau module. La persistance doit rester "
            "un import LOCAL, dans la fonction, pour que l'export PDF headless et les "
            "DAGs continuent de traduire sans base.")


def test_the_login_restores_the_choice():
    """Structure : `_hydrate_session` doit relire la préférence.

    Vérifié sur l'arbre plutôt qu'en simulant une connexion complète : le point qui
    compte est que la lecture se fasse APRÈS `session_state.clear()`, et c'est
    `_hydrate_session` qui en porte la garantie.
    """
    src = (_ROOT / "src/dashboard/auth.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next((f for f in ast.walk(tree)
               if isinstance(f, ast.FunctionDef) and f.name == "_hydrate_session"), None)
    assert fn is not None, "_hydrate_session a disparu — revoir ce garde"
    body = ast.get_source_segment(src, fn) or ""
    assert "load_preferred_lang" in body, (
        "la connexion ne restaure plus la langue choisie : l'artiste qui a mis "
        "l'anglais retrouvera le français à chaque connexion.")
