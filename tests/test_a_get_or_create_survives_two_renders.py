"""Guard: "get or create" must be one statement, not a SELECT that decides an INSERT.

Type: Utility
Uses: ast, threading, live Postgres
Triggers: pytest
Persists in: un locataire jetable, effacé en fin de test

Error class `check-then-insert-loses-the-race`.

Measured 2026-09-06 in CI. `referral._get_or_create_code` did `SELECT`, and on an
empty result `INSERT`. Two renders that cross read "no code" both times, insert both
times, and the second one raises `duplicate key value violates unique constraint
"referral_codes_artist_id_key"` — `referral.show()` crashed in the render smoke.

It is not a test-only condition, and that is the point. Streamlit re-executes the
whole script on every interaction, so a double-click, a second tab, or a rerun that
overlaps produce exactly this. The page an artist opens to find their referral code
is the page that crashes.

Measured with six concurrent callers on one tenant: the old form returned 3 codes and
raised 3 `UniqueViolation`; the fixed form returns 6 identical codes and raises none.
"""
from __future__ import annotations

import ast
import os
import socket
import threading
import uuid
from pathlib import Path

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


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


_VIEW = _repo_root() / "src" / "dashboard" / "views" / "referral.py"


def test_the_creation_is_a_single_statement():
    """AST: the function must not branch on a SELECT before inserting.

    Par l'AST et non par une recherche de chaîne : le docstring de la fonction
    corrigée CITE la requête d'origine pour expliquer le défaut, donc un
    `"SELECT code FROM" in source` serait rouge sur sa propre explication.
    """
    tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "_get_or_create_code"),
              None)
    assert fn is not None, "_get_or_create_code a disparu de la vue referral"

    queries = [a.value for n in ast.walk(fn)
               if isinstance(n, ast.Call)
               for a in n.args
               if isinstance(a, ast.Constant) and isinstance(a.value, str)]
    inserts = [q for q in queries if "INSERT INTO referral_codes" in q]
    assert inserts, "la fonction n'insère plus rien"
    assert all("ON CONFLICT" in q for q in inserts), (
        "un INSERT sans ON CONFLICT : deux rendus qui se croisent font planter la "
        "page sur la contrainte d'unicité")
    assert not [n for n in ast.walk(fn) if isinstance(n, ast.If)], (
        "la fonction re-branche sur un résultat de lecture avant d'écrire — c'est "
        "exactement le check-then-insert qui perdait la course")


@pytest.mark.skipif(_db() is None, reason="needs the provisioned DB")
def test_six_concurrent_renders_yield_one_code_and_no_error():
    """La mesure, pas la forme : six appels simultanés sur un locataire neuf."""
    from src.dashboard.utils import get_db_connection
    from src.dashboard.views.referral import _get_or_create_code

    admin = _db()
    slug = f"race-{uuid.uuid4().hex[:8]}"
    aid = admin.fetch_query(
        "INSERT INTO saas_artists (name, slug, tier, active) "
        "VALUES (%s, %s, 'free', TRUE) RETURNING id", (f"RACE {slug}", slug))[0][0]

    codes: list[str] = []
    errors: list[str] = []

    def worker():
        try:
            db = get_db_connection()
            codes.append(_get_or_create_code(db, aid))
            db.close()
        except Exception as exc:  # noqa: BLE001 — c'est l'objet de la mesure
            errors.append(repr(exc)[:200])

    try:
        threads = [threading.Thread(target=worker) for _ in range(6)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        assert not errors, f"la course lève encore : {errors}"
        assert len(codes) == 6, f"{len(codes)} appels sur 6 ont rendu un code"
        assert len(set(codes)) == 1, (
            f"six appels ont fabriqué {len(set(codes))} codes différents : "
            "l'artiste voit un code qui change d'un rafraîchissement à l'autre")
    finally:
        admin.execute_query("DELETE FROM referral_codes WHERE artist_id = %s", (aid,))
        admin.execute_query("DELETE FROM saas_artists WHERE id = %s", (aid,))
