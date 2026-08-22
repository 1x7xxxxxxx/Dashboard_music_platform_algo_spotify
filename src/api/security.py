"""Security middlewares for the FastAPI backend — C3 hardening.

Type: Sub
Uses: starlette middleware hooks (via src.api.main)
Triggers: every API request (sliding-window rate limit + response headers)

In-memory sliding-window rate limiter — deliberate minimalism (no Redis /
slowapi dependency, ADR-002 spirit): adequate for the single-process uvicorn
deployment. Counters reset on process restart.

The limiter and the X-Forwarded-For parser both live in
`src/utils/request_throttle.py` since 2026-08-22, because the dashboard needs the
same two things (R23 registration, R26 TOTP) and a second copy of a header parser
is how the hop-0 bypass would have survived its own fix. This file keeps the API's
budgets, its paths, and the middleware.
"""
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# One X-Forwarded-For parser and one limiter for the whole product — the dashboard
# imports the same two names (src/dashboard/utils/throttle.py). Re-exported here so
# `security.SlidingWindowLimiter` / `security.TRUSTED_PROXY_HOPS` keep working.
from src.utils.request_throttle import (  # noqa: F401 — re-exported
    TRUSTED_PROXY_HOPS,
    SlidingWindowLimiter,
    client_ip_from_headers,
)

# Global budget per client IP (all endpoints).
RATE_LIMIT_MAX = int(os.getenv("API_RATE_LIMIT_MAX", "120"))
RATE_LIMIT_WINDOW_SECS = int(os.getenv("API_RATE_LIMIT_WINDOW_SECS", "60"))
# Stricter budget for the credential endpoint (brute-force target).
AUTH_RATE_LIMIT_MAX = int(os.getenv("API_AUTH_RATE_LIMIT_MAX", "10"))
AUTH_RATE_LIMIT_WINDOW_SECS = int(os.getenv("API_AUTH_RATE_LIMIT_WINDOW_SECS", "300"))

_AUTH_PATH = "/auth/token"
_EXEMPT_PATHS = frozenset({"/health"})  # infra probes must never 429
# Swagger UI / ReDoc load JS from a CDN — a strict CSP would blank the docs.
_DOCS_PATHS = frozenset({"/docs", "/redoc", "/openapi.json"})

_GLOBAL_LIMITER = SlidingWindowLimiter(RATE_LIMIT_MAX, RATE_LIMIT_WINDOW_SECS)
_AUTH_LIMITER = SlidingWindowLimiter(AUTH_RATE_LIMIT_MAX, AUTH_RATE_LIMIT_WINDOW_SECS)


def client_ip(request: Request) -> str:
    """Client IP for rate-limiting — delegates to the shared parser.

    Kept as a named function because the middleware and
    `tests/test_rate_limit_client_ip.py` both address it, and because starlette's
    `request.client` is the only place the socket peer is reachable.
    """
    return client_ip_from_headers(
        request.headers.get,
        request.client.host if request.client else None,
    )


async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    if path not in _EXEMPT_PATHS:
        limiter = _AUTH_LIMITER if path == _AUTH_PATH else _GLOBAL_LIMITER
        retry_after = limiter.hit(f"{client_ip(request)}:{path == _AUTH_PATH}")
        if retry_after is not None:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please retry later."},
                headers={"Retry-After": str(retry_after)},
            )
    return await call_next(request)


async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    # Browsers ignore HSTS over plain HTTP, so always setting it is harmless locally.
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.url.path not in _DOCS_PATHS:
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault(
            "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
        )
    return response


def install(app: FastAPI) -> None:
    """Register both middlewares. Headers registered LAST → outermost,
    so 429 responses from the rate limiter also carry the security headers."""
    app.middleware("http")(rate_limit_middleware)
    app.middleware("http")(security_headers_middleware)
