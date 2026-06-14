"""External synthetic health probes of the LIVE production app, through Cloudflare.

Type: Utility
Uses: requests, ssl/socket (edge TLS), public + authenticated endpoints
Triggers: .github/workflows/prod-health.yml (daily) — set RUN_PROD_HEALTH=1
Depends on: production reachable via Cloudflare; B-probes need HEALTHCHECK_* creds
Persists in: nothing (read-only black-box checks)

These run ONLY when RUN_PROD_HEALTH=1 (the scheduled workflow). They are skipped
in normal CI so a push never hammers prod. Unlike internal checks (Airflow on the
box), these go THROUGH Cloudflare like a real client, so they catch edge/CF/cert/
DNS/routing regressions — e.g. the 2026-06-14 Bot Fight Mode 403 on the Stripe
webhook that every internal check missed.

Two layers:
  A — liveness, no secrets (always runs under RUN_PROD_HEALTH=1).
  B — authenticated probe of data endpoints vs the PROD schema (catches the
      schema-drift 500 class that CI, running on the canonical schema, cannot).
      Skips unless HEALTHCHECK_USER + HEALTHCHECK_PASSWORD are set.
"""

import os
import socket
import ssl
import time
from datetime import datetime, timezone

import pytest
import requests

APP_URL = os.getenv("PROD_APP_URL", "https://streamlytics.fr")
API_URL = os.getenv("PROD_API_URL", "https://api.streamlytics.fr")
HEALTHCHECK_USER = os.getenv("HEALTHCHECK_USER")
HEALTHCHECK_PASSWORD = os.getenv("HEALTHCHECK_PASSWORD")

_TIMEOUT = 15
_RETRIES = 3

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PROD_HEALTH") != "1",
    reason="prod probes run only in the scheduled workflow (RUN_PROD_HEALTH=1)",
)


def _request(method: str, url: str, **kwargs) -> requests.Response:
    """Issue an HTTP request through Cloudflare, retrying transient network errors."""
    last_exc: Exception | None = None
    for attempt in range(_RETRIES):
        try:
            return requests.request(method, url, timeout=_TIMEOUT, **kwargs)
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(2 * (attempt + 1))
    raise AssertionError(f"{method} {url} unreachable after {_RETRIES} tries: {last_exc}")


def _cert_days_remaining(host: str) -> int:
    """Days until the edge TLS certificate served for `host` expires."""
    ctx = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=_TIMEOUT) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as ssock:
            cert = ssock.getpeercert()
    not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(
        tzinfo=timezone.utc
    )
    return (not_after - datetime.now(timezone.utc)).days


# ─────────────────────────── A — liveness (no secrets) ───────────────────────────

def test_dashboard_is_up() -> None:
    r = _request("GET", f"{APP_URL}/")
    assert r.status_code == 200, f"dashboard returned {r.status_code}"


def test_api_health_is_up() -> None:
    r = _request("GET", f"{API_URL}/health")
    assert r.status_code == 200, f"/health returned {r.status_code}"


def test_stripe_webhook_reachable_not_edge_blocked() -> None:
    # Regression guard (2026-06-14): Cloudflare Bot Fight Mode 403'd this M2M path,
    # silently breaking Stripe subscription sync. An empty body must REACH the app
    # and be rejected for a bad signature (400) — never edge-challenged (403/cf-mitigated).
    r = _request(
        "POST", f"{API_URL}/webhooks/stripe", json={}, headers={"Content-Type": "application/json"}
    )
    assert "cf-mitigated" not in {k.lower() for k in r.headers}, (
        "Cloudflare is challenging the Stripe webhook (M2M blocked) — re-check Bot Fight Mode "
        "/ IP allowlist (see .claude/dev-docs/cloudflare-stripe-webhook-allowlist.md)"
    )
    assert r.status_code == 400, f"webhook returned {r.status_code}, expected 400 (bad signature)"


def test_auth_token_reaches_app_not_edge_blocked() -> None:
    r = _request(
        "POST", f"{API_URL}/auth/token",
        data={"username": "healthcheck-probe", "password": "wrong"},  # pragma: allowlist secret
    )
    assert r.status_code != 403, "auth endpoint edge-blocked (403) — programmatic clients can't reach it"
    assert r.status_code in (400, 401, 422), f"auth returned {r.status_code}, expected 401-class"


def test_https_redirect() -> None:
    r = _request("GET", "http://streamlytics.fr/", allow_redirects=False)
    assert r.status_code in (301, 302, 307, 308), f"http did not redirect ({r.status_code})"
    assert r.headers.get("location", "").startswith("https://"), "redirect target is not https"


def test_security_headers_present() -> None:
    r = _request("GET", f"{API_URL}/health")
    headers = {k.lower(): v for k, v in r.headers.items()}
    assert "strict-transport-security" in headers, "missing HSTS header"
    assert headers.get("x-content-type-options", "").lower() == "nosniff", "missing nosniff"
    assert headers.get("x-frame-options", "").upper() == "DENY", "missing X-Frame-Options: DENY"


def test_openapi_disabled_in_prod() -> None:
    # Pentest invariant: the API schema map must not be public (API_ENABLE_DOCS unset).
    r = _request("GET", f"{API_URL}/openapi.json")
    assert r.status_code == 404, f"/openapi.json exposed ({r.status_code}) — must be 404 in prod"


def test_docs_disabled_in_prod() -> None:
    r = _request("GET", f"{API_URL}/docs")
    assert r.status_code == 404, f"/docs exposed ({r.status_code}) — must be 404 in prod"


@pytest.mark.parametrize("host", ["streamlytics.fr", "api.streamlytics.fr"])
def test_edge_tls_cert_not_expiring(host: str) -> None:
    days = _cert_days_remaining(host)
    assert days > 14, f"{host} edge TLS cert expires in {days} days"


# ──────────── B — authenticated data-endpoint probe vs the PROD schema ────────────

@pytest.fixture(scope="module")
def auth_header() -> dict:
    """Log the healthcheck service account in once; skip B-probes if creds absent."""
    if not (HEALTHCHECK_USER and HEALTHCHECK_PASSWORD):
        pytest.skip("HEALTHCHECK_USER/HEALTHCHECK_PASSWORD not set — authenticated probes skipped")
    r = _request(
        "POST",
        f"{API_URL}/auth/token",
        data={"username": HEALTHCHECK_USER, "password": HEALTHCHECK_PASSWORD},
    )
    assert r.status_code == 200, f"healthcheck login failed: {r.status_code} {r.text[:200]}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.parametrize("path", ["/kpis", "/youtube/videos", "/streams/summary", "/ml/predictions"])
def test_data_endpoint_no_500_against_prod_schema(path: str, auth_header: dict) -> None:
    # Catches prod-only schema drift (the /kpis & /youtube/videos 500s) that CI,
    # running on the canonical schema, structurally cannot see.
    r = _request("GET", f"{API_URL}{path}", headers=auth_header)
    assert r.status_code != 500, f"{path} → 500 (prod schema drift?) body={r.text[:200]}"
    assert r.status_code == 200, f"{path} returned {r.status_code}, expected 200"
