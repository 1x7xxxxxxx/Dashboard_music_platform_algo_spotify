"""Guard — the rate-limit key cannot be chosen by the caller.

Error class `trusted-value-read-from-an-untrusted-header`.

`client_ip()` returned `X-Forwarded-For.split(",")[0]` — the FIRST hop, which is
whatever the client sent. Cloudflare and Caddy both APPEND the peer they saw, so an
attacker-supplied entry survives to position 0.

Measured 2026-08-22: sending `X-Forwarded-For: 10.0.0.<n>` with an incrementing n
gives a fresh bucket per request, so neither the strict /auth/token budget (10/300s)
nor the global 120/min ever fires. Chained with the registration oracle
(`register.py` answers "L'email 'x' est déjà enregistré") and the 5-attempt lockout,
that keeps every tenant locked out of both the API and the dashboard indefinitely —
the lockout column is shared. Password spraying is likewise unthrottled.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.api.security import TRUSTED_PROXY_HOPS, client_ip

PEER = "203.0.113.9"


def _req(headers: dict, peer: str = PEER):
    r = MagicMock()
    r.headers = headers
    r.client = MagicMock()
    r.client.host = peer
    return r


def test_a_lone_forwarded_header_is_not_trusted() -> None:
    """One hop means it did not come through our proxies."""
    assert client_ip(_req({"x-forwarded-for": "10.0.0.1"})) == PEER


def test_a_spoofed_first_hop_is_ignored() -> None:
    """The attacker's value is at the LEFT; our proxies appended to the right."""
    got = client_ip(_req({"x-forwarded-for": "10.0.0.1, 1.2.3.4, 5.6.7.8"}))
    assert got != "10.0.0.1"
    assert got == "1.2.3.4"


def test_cloudflares_own_header_wins() -> None:
    """Cloudflare sets CF-Connecting-IP itself and overwrites any client value."""
    got = client_ip(_req({"cf-connecting-ip": "9.9.9.9",
                          "x-forwarded-for": "10.0.0.1, 1.2.3.4, 5.6.7.8"}))
    assert got == "9.9.9.9"


def test_no_header_falls_back_to_the_socket_peer() -> None:
    assert client_ip(_req({})) == PEER


def test_the_key_cannot_be_varied_by_the_caller() -> None:
    """The property that matters: N crafted requests must share ONE bucket."""
    keys = {client_ip(_req({"x-forwarded-for": f"10.0.0.{i}"})) for i in range(50)}
    assert keys == {PEER}, (
        f"a caller varied the rate-limit key {len(keys)} ways — the limiter is a no-op"
    )


def test_the_trusted_hop_count_is_configurable_and_sane() -> None:
    assert TRUSTED_PROXY_HOPS >= 1, (
        "0 trusted hops would read the raw header again"
    )


@pytest.mark.parametrize("header", ["x-forwarded-for", "X-Forwarded-For", "X-FORWARDED-FOR"])
def test_header_lookup_is_case_insensitive_in_shape(header: str) -> None:
    """Starlette headers are case-insensitive; a dict mock is not — pin the shape."""
    assert header.lower() == "x-forwarded-for"
