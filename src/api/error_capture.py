"""Every unhandled API exception becomes a defect in `app_error_log`, like the dashboard's.

Type: Utility
Uses: src/utils/error_registry.record_error, src/database/postgres_handler
Triggers: src/api/main.py (install_error_registry)
Persists in: app_error_log

R265 (owner notes L67-69 : « API et DAG dans app_error_log »). The registry that
`make error-inbox` reads was fed by the dashboard alone: a route that raised gave a 500 and
a log line, never a defect with a fingerprint and an occurrence count.

Critic verdict (critic-2026-09-27.md, R265 b) — « sans fausser les statuts HTTP mesurés ».
A handler for `Exception` is served by Starlette's OUTERMOST middleware
(`ServerErrorMiddleware`): the metrics middleware inside it still sees the exception
propagate, exactly as before, so the measured 500s are unchanged. The response is the
same bare 500 — no message, no traceback reaches the client. The handler opens its own
connection from the pool and closes it on every path.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _record(request, exc: BaseException) -> None:
    from src.database.postgres_handler import PostgresHandler
    from src.utils.error_registry import record_error
    from src.utils.safe_error import safe_error
    # A DATABASE failure is not written to the database: it would repeat the failure and
    # hold a request thread on a connect timeout for nothing (security-specialist, R265).
    if type(exc).__name__ in ("OperationalError", "InterfaceError", "PoolError"):
        return
    db = None
    try:
        db = PostgresHandler.from_env_or_config()
        route = request.scope.get("route")
        # The route TEMPLATE, never the raw path: without a matched route the path is the
        # caller's text, and it would land in the inbox and the evening mail.
        page = f"api:{getattr(route, 'path', None) or '<unmatched>'}"
        record_error(db, page, exc, environment="api")
    except Exception as err:      # noqa: BLE001 — the registry never masks the 500
        logger.error("api error registry: %s", safe_error(err))
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:      # noqa: BLE001
                pass


def install_error_registry(app) -> None:
    from fastapi.responses import PlainTextResponse

    # A plain `def`, NOT `async def` (security-specialist, R265, HIGH): `_record` is
    # synchronous psycopg2 — up to 5 s to connect and 15 s of statement_timeout. On the
    # event loop of the API's single process it froze every request, `/health` included.
    # Starlette runs a sync exception handler in its threadpool.
    @app.exception_handler(Exception)
    def _unhandled(request, exc):      # noqa: ANN001 — Starlette signature
        _record(request, exc)
        return PlainTextResponse("Internal Server Error", status_code=500)
