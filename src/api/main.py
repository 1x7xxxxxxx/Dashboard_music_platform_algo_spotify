"""FastAPI REST backend — Brick 14.

Exposes the core platform data over a JWT-authenticated REST API.

Run locally (development):
    uvicorn src.api.main:app --reload --port 8502

OpenAPI docs (Swagger UI): http://localhost:8502/docs
ReDoc:                      http://localhost:8502/redoc

Authentication flow:
    1. POST /auth/token  with form fields username + password (same creds as Streamlit dashboard)
    2. Use the returned ``access_token`` as a Bearer token on all other endpoints.

Environment variables:
    API_SECRET_KEY   — JWT signing secret (override in production, min 32 chars)
    DATABASE_URL     — optional postgres:// URL; falls back to config/config.yaml
"""
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so src.* imports resolve
_root = str(Path(__file__).resolve().parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from src.api.routers import auth, artists, streams, youtube, ml, kpis, stripe_webhook  # noqa: E402
from src.api.security import install as install_security  # noqa: E402

def _preflight() -> None:
    """Fail loud in prod on weak/absent security-critical config — instead of silently
    degrading (API_SECRET_KEY falls back to an EPHEMERAL key in auth.py, so JWTs die on
    every restart / differ per worker). Warns by default so dev/test keep working; raises
    only under API_STRICT_BOOT=1 (set in the prod compose). Mirrors the dashboard's
    boot-time FERNET/AIRFLOW checks."""
    import logging
    problems = []
    if len(os.getenv("API_SECRET_KEY", "")) < 32:
        problems.append("API_SECRET_KEY missing or <32 chars — JWTs won't survive a "
                        "restart / multi-worker (set `openssl rand -hex 32`)")
    if not os.getenv("DATABASE_URL"):
        problems.append("DATABASE_URL not set")
    if not problems:
        return
    msg = "API startup preflight: " + "; ".join(problems)
    if os.getenv("API_STRICT_BOOT"):
        raise RuntimeError(msg + " — refusing to start (API_STRICT_BOOT=1).")
    logging.getLogger("api.preflight").warning(
        "⚠️ %s — set API_STRICT_BOOT=1 in prod to make this fatal.", msg)


_preflight()

# OpenAPI docs (/docs, /redoc) hand attackers the full API surface map — disabled by
# default on a public deploy. Set API_ENABLE_DOCS=1 to re-enable (local dev).
_docs_enabled = os.getenv("API_ENABLE_DOCS") == "1"

app = FastAPI(
    title="Music Platform API",
    description=(
        "REST API for the music analytics SaaS platform.\n\n"
        "All endpoints (except `/auth/token` and `/health`) require a Bearer JWT obtained via `POST /auth/token`."
    ),
    version="1.0.0",
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    # Gate the raw schema too: with docs/redoc off but openapi_url at its default,
    # /openapi.json still served the full API map (endpoints + schemas) to anyone —
    # pentest 2026-06-13 finding. None → /openapi.json returns 404 in prod.
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# C3 hardening: sliding-window rate limit + security response headers
install_security(app)

# CORS origins from env (comma-separated) so the real HTTPS origin is allowlisted in
# production; falls back to localhost for dev. Never use "*" with allow_credentials.
_cors_origins = [
    o.strip() for o in os.getenv(
        "CORS_ORIGINS", "http://localhost:8501,http://localhost:3000"
    ).split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(artists.router)
app.include_router(streams.router)
app.include_router(youtube.router)
app.include_router(ml.router)
app.include_router(kpis.router)
app.include_router(stripe_webhook.router)


@app.get("/health", tags=["meta"], summary="Health check")
def health():
    """Returns ``{"status": "ok"}`` — no auth required."""
    return {"status": "ok"}
