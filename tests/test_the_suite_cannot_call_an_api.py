"""
Guard — the boundary that stops a test from calling a real API must actually bite.

Type: Sub
Uses: socket, pytest
Triggers: pytest
Depends on: tests/conftest.py::_no_real_http
Persists in: nothing

Error class: test-calls-a-real-api.

R41. Khorikov (*Unit Testing Principles*, p.213/221) draws the line this repo followed
only halfway: MANAGED dependencies (the database) are used for real — correctly — while
UNMANAGED ones, out-of-process and observable from outside, "are part of your system's
observable behavior. Such dependencies should be mocked out."

Measured 2026-08-23 with a tripwire on `socket.connect` across a full run:
`test_artist_preflight.py::test_a_scoped_run_still_requires_its_own_platform` opened four
real outbound connections — Meta, Google and SoundCloud — because `step_central_apps`
probes all four platforms, out-of-scope ones included, with the credentials in `.env`.

Why this outlived its SMTP twin by a day: an email lands in an inbox and is seen. A real
HTTP call leaves no trace for the operator — it spends quota, may write, and fails in CI
the moment there is no network.

The boundary sits on the SOCKET rather than on `requests`, because the collectors reach
the network through `requests`, `googleapiclient` and `urllib` depending on the platform;
patching one would have let the other two out. Ports 80/443 only: Postgres on 5433 is a
managed dependency and must keep working.
"""

import socket

import pytest


def test_a_test_cannot_open_a_real_http_connection(request) -> None:
    with pytest.raises(ConnectionRefusedError):
        socket.socket().connect(("example.invalid", 443))

    attempts = getattr(request.node, "_http_attempts", None)
    assert attempts == ["example.invalid:443"], (
        "the HTTP boundary refused the connection but did not RECORD it — a collector "
        "that swallows the exception would leave the offending test green"
    )
    attempts.clear()          # consumed: this test meant to trip the boundary


def test_plain_http_is_blocked_too(request) -> None:
    with pytest.raises(ConnectionRefusedError):
        socket.socket().connect(("example.invalid", 80))
    request.node._http_attempts.clear()


def test_the_database_port_is_not_blocked(request) -> None:
    """Postgres is a MANAGED dependency: the boundary must not touch it.

    A boundary that also cut 5433 would turn ~160 tenant-isolation tests into silent
    skips — the exact failure this repo already documents for the database gate. The
    connection here is expected to fail (nothing listens on that port) but with a
    CONNECTION error from the OS, never with the boundary's refusal.
    """
    sock = socket.socket()
    sock.settimeout(0.5)
    try:
        sock.connect(("127.0.0.1", 5599))     # port fermé, choisi hors de tout service
    except ConnectionRefusedError as exc:
        assert "conftest" not in str(exc), (
            "the boundary refused a non-HTTP port — it must only block 80/443"
        )
    except OSError:
        pass                                   # timeout / unreachable : très bien
    finally:
        sock.close()
    assert not getattr(request.node, "_http_attempts", []), (
        "a non-HTTP port was recorded as an HTTP attempt"
    )
