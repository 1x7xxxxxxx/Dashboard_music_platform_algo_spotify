"""Security middlewares for the FastAPI backend — C3 hardening.

Type: Sub
Uses: starlette middleware hooks (via src.api.main)
Triggers: every API request (sliding-window rate limit + response headers)

In-memory sliding-window rate limiter — deliberate minimalism (no Redis /
slowapi dependency, ADR-002 spirit): adequate for the single-process uvicorn
deployment. Counters reset on process restart. Behind a reverse proxy
(Railway), the client IP is read from the first X-Forwarded-For hop — only
trustworthy when a proxy actually sets it.
"""
import os
import time
from collections import deque
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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

_MAX_TRACKED_CLIENTS = 10_000  # memory bound — full reset beyond this


class SlidingWindowLimiter:
    """Per-key sliding-window counter. Returns a Retry-After when over budget."""

    def __init__(self, max_requests: int, window_secs: int):
        self.max_requests = max_requests
        self.window_secs = window_secs
        self._hits: dict[str, deque] = {}

    def hit(self, key: str, now: Optional[float] = None) -> Optional[int]:
        """Record a request for `key`. None = allowed; int = seconds to wait."""
        now = time.time() if now is None else now
        if len(self._hits) > _MAX_TRACKED_CLIENTS:
            self._hits.clear()
        window = self._hits.setdefault(key, deque())
        cutoff = now - self.window_secs
        while window and window[0] <= cutoff:
            window.popleft()
        if len(window) >= self.max_requests:
            return max(1, int(window[0] + self.window_secs - now) + 1)
        window.append(now)
        return None


_GLOBAL_LIMITER = SlidingWindowLimiter(RATE_LIMIT_MAX, RATE_LIMIT_WINDOW_SECS)
_AUTH_LIMITER = SlidingWindowLimiter(AUTH_RATE_LIMIT_MAX, AUTH_RATE_LIMIT_WINDOW_SECS)


def client_ip(request: Request) -> str:
    """Client IP — first X-Forwarded-For hop behind a proxy, else the socket peer."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


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
