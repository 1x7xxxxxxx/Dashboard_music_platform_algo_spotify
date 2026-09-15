"""One place that answers "is there a provisioned Postgres?".

The same 25-line probe was copy-pasted into five test modules, each with its own
comment explaining the same two subtleties. A test that needs the live schema now
writes one line:

    (Recompté le 2026-09-15 : **29** modules passent désormais par cette porte, et
    **50** importent encore `get_db_connection` — la porte LOURDE, qui tire Streamlit.
    Les deux ensembles se recouvrent largement : importer les deux ne fait économiser
    aucun des 5,30 s. Le « cinq » ci-dessus est l'état du jour où ce fichier a été
    écrit, gardé parce qu'il dit d'où l'on vient ; il ne décrit plus le dépôt.)

    pytestmark = requires_live_db()

Both subtleties stay in force, in one place:

  * a TCP check alone is not enough — CI can start an EMPTY `postgres:17` on 5433,
    so the socket connects while every query fails on a missing relation. The
    authoritative probe reads a core table.
  * when `DATABASE_URL` is set (CI, or a throwaway container on another port) the
    hardcoded 5433 pre-check must be skipped, or the module skips on a DB that is
    actually there.
"""
from __future__ import annotations

import os
import socket
from functools import lru_cache

import pytest

DB_HOST, DB_PORT = "127.0.0.1", 5433

_SKIP_REASON = (
    f"No provisioned Postgres on {DB_HOST}:{DB_PORT} (socket down or schema not "
    "migrated), and no DATABASE_URL — this suite needs the live schema"
)


@lru_cache(maxsize=1)
def db_ready() -> bool:
    """True when a Postgres carrying THIS app's schema is reachable.

    ── Pourquoi un cache (2026-09-15) ──
    `requires_live_db()` est évalué au moment de l'IMPORT de chaque module qui le
    porte, et **22 modules** le portent. Sans cache, la seule collecte ouvrait donc
    22 connexions Postgres — et, quand la base est absente, payait 22 fois le
    `timeout=1.5 s` du pré-test de socket, soit **33 s de collecte pour apprendre
    22 fois la même chose**. Sous `-n 8`, chaque worker recommençait.

    La réponse ne peut pas changer à l'intérieur d'un processus pytest : la base est
    là ou elle ne l'est pas quand la session démarre, et aucun test ne provisionne un
    Postgres en cours de route. Mettre le résultat en cache ne perd donc aucune
    information — c'est la même question, posée une fois.

    `maxsize=1` : la fonction ne prend pas d'argument, il n'y a qu'une réponse.
    `db_ready.cache_clear()` reste disponible pour un test qui voudrait la reposer.
    """
    if not os.environ.get("DATABASE_URL"):
        try:
            with socket.create_connection((DB_HOST, DB_PORT), timeout=1.5):
                pass
        except OSError:
            return False
    try:
    # ── Pourquoi la porte PARTAGÉE et non `get_db_connection` (2026-09-15) ──
    # `from src.dashboard.utils import get_db_connection` exécute
    # `src/dashboard/utils/__init__.py`, dont la ligne 1 est `import streamlit`.
    # Mesuré : **5,30 s**, contre **0,19 s** pour `src.database.postgres_handler`.
    # Ce coût était payé par CHAQUE processus pytest — et par chacun des 8 workers.
    #
    # Ce n'est pas un contournement de la règle « une seule porte »
    # (`tests/test_one_door_onto_the_database.py`) : la porte EST
    # `PostgresHandler.from_env_or_config()`, qui connaît les trois sources
    # (`DATABASE_URL` → `DATABASE_*` → `config.yaml`). `get_db_connection` ne fait
    # que l'appeler et y ajouter une bannière rouge Streamlit — dont un test n'a
    # aucun usage.
        from src.database.postgres_handler import PostgresHandler
        db = PostgresHandler.from_env_or_config()
        if db is None:
            return False
        try:
            db.fetch_query("SELECT 1 FROM saas_artists LIMIT 1")
            return True
        finally:
            db.close()
    except Exception:
        return False


def requires_live_db():
    """Module-level marker: `pytestmark = requires_live_db()`."""
    return pytest.mark.skipif(not db_ready(), reason=_SKIP_REASON)
