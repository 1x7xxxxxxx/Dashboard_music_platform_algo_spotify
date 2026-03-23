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
import sys
from pathlib import Path

# Ensure project root is on sys.path so src.* imports resolve
_root = str(Path(__file__).resolve().parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from src.api.routers import auth, artists, streams, youtube, ml, kpis, stripe_webhook  # noqa: E402

app = FastAPI(
    title="Music Platform API",
    description=(
        "REST API for the music analytics SaaS platform.\n\n"
        "All endpoints (except `/auth/token` and `/health`) require a Bearer JWT obtained via `POST /auth/token`."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow the local Streamlit dashboard and any future frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",  # Streamlit dashboard
        "http://localhost:3000",  # potential React frontend
    ],
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
