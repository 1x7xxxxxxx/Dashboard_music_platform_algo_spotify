"""The one place a raw psycopg2 connection to `spotify_etl` is built.

Type: Utility
Uses: psycopg2 (imported lazily), src.utils.config_loader (lazily, last resort)
Depends on: DATABASE_URL, or DATABASE_HOST/PORT/NAME/USER/PASSWORD, or config.yaml
Persists in: nothing

Four modules built their own DSN, and they did not agree. Measured 2026-08-21:

    credential_loader   env vars, host default 'localhost'   (×4 copies)
    circuit_breaker     env vars, host default 'postgres'
    dag_run_logger      env vars, host default 'postgres'
    stripe_webhook      DATABASE_URL, then config.yaml

That split mirrors a real one in production — Airflow gets `DATABASE_HOST=postgres`
and no `DATABASE_URL`; the api and dashboard containers get `DATABASE_URL` and no
`DATABASE_HOST`. So each factory worked *where it happened to run*, and none of
them worked in the other place. `credential_loader` is imported only by DAGs and
collectors today, which is the sole reason its `localhost` default has never been
hit; the first import from a dashboard view would have found it.

This resolves all three sources, in the order of specificity, so a caller no
longer has to know which container it is in:

    1. `DATABASE_URL`     — how api/dashboard are configured
    2. `DATABASE_*` vars  — how Airflow is configured
    3. `config.yaml`      — the local developer path

`psycopg2` is imported inside the function on purpose: this module is reachable
from Airflow DAG parsing, where an import error at module scope takes down the
whole DAG file instead of the one task that needed a database.
"""
from __future__ import annotations

import os

# The port a bare local checkout publishes. Containers always set DATABASE_PORT
# (5432, internal), so this default only applies outside them — and outside them
# this repo's compose maps 5433, never 5432. Hardcoding 5432 is the mistake
# `check_env.py` made until it learned to read the port from compose.
_LOCAL_FALLBACK_PORT = 5433


def dsn_source() -> str:
    """Which of the three sources will be used. For diagnostics, never for logic."""
    if os.getenv("DATABASE_URL"):
        return "DATABASE_URL"
    if os.getenv("DATABASE_HOST"):
        return "env"
    return "config.yaml"


def _config_kwargs() -> dict | None:
    """Connection kwargs from config.yaml, or None when it is not usable."""
    try:
        from src.utils.config_loader import config_loader
        db = (config_loader.load() or {}).get("database")
    except Exception:
        return None
    if not isinstance(db, dict) or not db.get("host"):
        return None
    return {
        "host": db["host"],
        "port": int(db.get("port", _LOCAL_FALLBACK_PORT)),
        "database": db.get("database", "spotify_etl"),
        "user": db.get("user", "postgres"),
        "password": db.get("password", ""),
    }


def resolve_kwargs() -> dict:
    """Connection keywords from the env vars, else config.yaml. Raises if neither.

    Split out of `connect()` so `PostgresHandler.from_env()` shares the exact same
    precedence instead of restating it — the restating is what produced the
    `localhost` / `postgres` divergence in the first place. `DATABASE_URL` is NOT
    handled here: it is a DSN string, not keywords, and each caller has its own
    door for it (`psycopg2.connect(url)` / `PostgresHandler.from_url`).
    """
    host = os.getenv("DATABASE_HOST")
    if host:
        return {
            "host": host,
            "port": int(os.getenv("DATABASE_PORT", 5432)),
            "database": os.getenv("DATABASE_NAME", "spotify_etl"),
            "user": os.getenv("DATABASE_USER", "postgres"),
            "password": os.getenv("DATABASE_PASSWORD", ""),
        }
    kwargs = _config_kwargs()
    if kwargs is None:
        raise RuntimeError(
            "No database configuration: set DATABASE_URL, or DATABASE_HOST "
            "(+ PORT/NAME/USER/PASSWORD), or provide config/config.yaml. "
            "Copy config/config.example.yaml to start."
        )
    return kwargs


def connect(autocommit: bool = False):
    """Open a connection to the application database.

    Raises whatever psycopg2 raises — a caller that wants "None on failure" wraps
    this in its own try/except and says so. A connection helper that swallows its
    own failure is how a database outage turns into "no rows", which is the class
    `.claude/rules/python.md` forbids: a read that fails must not look like a read
    that found nothing.
    """
    import psycopg2

    url = os.getenv("DATABASE_URL")
    conn = psycopg2.connect(url) if url else psycopg2.connect(**resolve_kwargs())
    conn.autocommit = autocommit
    return conn
