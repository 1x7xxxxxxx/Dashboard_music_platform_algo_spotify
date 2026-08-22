"""Client-IP resolution and sliding-window throttling, shared by the API and the dashboard.

Type: Utility
Uses: nothing (stdlib only — must be importable from FastAPI middleware and Streamlit views)
Triggers: every rate-limited request on either surface
Persists in: nothing (in-process counters)

Why this module exists — 2026-08-22.

Both halves of this logic already existed, in `src/api/security.py`, and both were
reachable only from FastAPI: `client_ip()` took a `starlette.Request`, and the limiter
was instantiated at API import time. The dashboard therefore had no throttle at all
beyond a `st.session_state` counter, which a new browser tab resets (R26), and the
public registration page had none whatsoever (R23).

Copying the header logic into the dashboard would have created a second X-Forwarded-For
parser. That is the failure this file prevents: the API's parser was wrong until
2026-08-22 (it read hop 0, the one the *client* controls, making the limiter a no-op),
and a copy made before the fix would still be wrong today with nothing to point at it.
One parser, two callers, one test suite.

The counters are per-process and reset on restart — deliberate, same reasoning as the
API's (ADR-002 spirit: no Redis for a single-process deployment). Both the uvicorn API
and the Streamlit dashboard run as one process each, so "per process" is "per surface".
"""
from __future__ import annotations

import os
import time
from collections import deque
from typing import Callable, Optional

# Number of proxies in front of us whose X-Forwarded-For entries we trust.
# Production is Cloudflare → Caddy → app, so the last TWO hops are ours.
TRUSTED_PROXY_HOPS = int(os.getenv("TRUSTED_PROXY_HOPS", "2"))

_MAX_TRACKED_CLIENTS = 10_000  # memory bound — full reset beyond this


def client_ip_from_headers(
    get_header: Callable[[str], Optional[str]],
    peer: Optional[str] = None,
) -> str:
    """Client IP, taken from the RIGHT of X-Forwarded-For — never the left.

    `get_header` is a case-insensitive single-header lookup returning None when absent
    (`request.headers.get` on starlette, `st.context.headers.get` on Streamlit — both
    already fold case). `peer` is the socket peer when the caller can see one.

    The first hop is whatever the CLIENT sent. Cloudflare and Caddy both APPEND the peer
    they saw, so an attacker-supplied entry survives to the app at position 0. Reading it
    made the API rate limiter a no-op: `X-Forwarded-For: 10.0.0.<n>` with an incrementing
    n created a fresh bucket per request. Measured 2026-08-22.

    Cloudflare's `CF-Connecting-IP` is preferred when present: Cloudflare sets it itself
    and overwrites any client-supplied value.
    """
    cf = get_header("cf-connecting-ip")
    if cf:
        return cf.strip()
    forwarded = get_header("x-forwarded-for")
    if forwarded:
        hops = [h.strip() for h in forwarded.split(",") if h.strip()]
        # FEWER hops than we expect means the header did not come through our proxies —
        # so it is not ours to read. Falling back to the socket peer is the only safe
        # answer; taking hops[0] there would restore the bypass in every environment
        # that has one proxy instead of two.
        if len(hops) >= TRUSTED_PROXY_HOPS > 0:
            return hops[len(hops) - TRUSTED_PROXY_HOPS]
    return peer or "unknown"


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

    def peek(self, key: str, now: Optional[float] = None) -> Optional[int]:
        """Seconds to wait if `key` is over budget, without recording a hit.

        For call sites that must decide *before* doing work whether to proceed, and
        record the attempt only on the path that actually consumed something.
        """
        now = time.time() if now is None else now
        window = self._hits.get(key)
        if not window:
            return None
        cutoff = now - self.window_secs
        while window and window[0] <= cutoff:
            window.popleft()
        if len(window) >= self.max_requests:
            return max(1, int(window[0] + self.window_secs - now) + 1)
        return None

    def reset(self, key: str) -> None:
        """Forget `key`'s history — call after a *successful* authentication only."""
        self._hits.pop(key, None)
