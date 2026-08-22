"""Per-IP throttling for the dashboard's unauthenticated and pre-authenticated forms.

Type: Utility
Uses: src.utils.request_throttle (shared with the FastAPI middleware)
Triggers: registration submit (R23), TOTP challenge submit (R26), login submit
Persists in: nothing (in-process counters, reset on restart)

Why not `st.session_state` — measured 2026-08-22.

`src/dashboard/auth.py` already had `_check_session_rate_limit()`, and it counts in
`st.session_state`. A Streamlit session is one browser tab: opening a second tab, or
clearing the cookie, produces a fresh counter. That made it a UX guard against
fat-fingering, never a security control — which is precisely how the TOTP challenge
stayed brute-forceable (R26) even though it *looked* rate-limited.

These buckets are keyed by client IP instead, in module state, so they survive a new
tab and a new session. They are per-process, which for Streamlit means per container:
the same reasoning (and the same limitation) as the API's, see ADR-002.

An IP is not an identity. A NAT'd office shares one bucket and a botnet defeats it.
The budgets below are therefore sized to stop *scripted enumeration from one host*,
not to be a CAPTCHA — they leave room for a household to register several accounts.
"""
from __future__ import annotations

import os
from typing import Optional

from src.utils.request_throttle import SlidingWindowLimiter, client_ip_from_headers

# Registration submits per IP. Sized for "a family signs up on the same wifi", not for
# "a script probes 24 bits of promo code": at 8 per 10 min, exhausting `token_hex(3)`
# takes ~40 years from one host.
REGISTER_MAX = int(os.getenv("DASHBOARD_REGISTER_MAX", "8"))
REGISTER_WINDOW_SECS = int(os.getenv("DASHBOARD_REGISTER_WINDOW_SECS", "600"))

# TOTP code submits per IP. A 6-digit code with valid_window=1 spans 3 codes out of
# 10^6; at 10 tries per 15 min the expected time to hit one is measured in centuries.
TOTP_MAX = int(os.getenv("DASHBOARD_TOTP_MAX", "10"))
TOTP_WINDOW_SECS = int(os.getenv("DASHBOARD_TOTP_WINDOW_SECS", "900"))

# Password submits per IP — a backstop *in front of* the per-account DB lockout, which
# an attacker spraying one password across many accounts never triggers.
LOGIN_MAX = int(os.getenv("DASHBOARD_LOGIN_MAX", "30"))
LOGIN_WINDOW_SECS = int(os.getenv("DASHBOARD_LOGIN_WINDOW_SECS", "900"))

_LIMITERS: dict[str, SlidingWindowLimiter] = {
    "register": SlidingWindowLimiter(REGISTER_MAX, REGISTER_WINDOW_SECS),
    "totp": SlidingWindowLimiter(TOTP_MAX, TOTP_WINDOW_SECS),
    "login": SlidingWindowLimiter(LOGIN_MAX, LOGIN_WINDOW_SECS),
}


def dashboard_client_ip() -> str:
    """Client IP of the current Streamlit request, or "unknown" outside a request.

    `st.context.headers` is unavailable in bare-script and test contexts (the same
    caveat `src/dashboard/utils/os_hints.py` documents), so this never raises. Falling
    back to a single "unknown" bucket is the safe direction: every headerless caller
    shares one budget rather than each getting a private one.
    """
    try:
        import streamlit as st

        headers = st.context.headers
        if headers is None:
            return "unknown"
        return client_ip_from_headers(headers.get)
    except Exception:  # no request context, or a Streamlit version without st.context
        return "unknown"


def throttle_check(bucket: str, key: Optional[str] = None) -> Optional[int]:
    """Seconds to wait if `bucket` is over budget for this client, else None.

    Does NOT consume budget — pair it with `throttle_record()` on the path that
    actually did the work, so a request rejected for another reason (an empty form,
    a mistyped password already counted elsewhere) is not billed twice.
    """
    return _LIMITERS[bucket].peek(_key(bucket, key))


def throttle_record(bucket: str, key: Optional[str] = None) -> None:
    """Consume one unit of `bucket`'s budget for this client."""
    _LIMITERS[bucket].hit(_key(bucket, key))


def throttle_reset(bucket: str, key: Optional[str] = None) -> None:
    """Forget this client's history in `bucket` — successful authentication only."""
    _LIMITERS[bucket].reset(_key(bucket, key))


def _key(bucket: str, key: Optional[str]) -> str:
    return f"{bucket}:{key or ''}:{dashboard_client_ip()}"
