"""Streamlit must ping, because Cloudflare closes an idle websocket.

Type: Test
Uses: tomllib
Depends on: .streamlit/config.toml
Persists in: nothing

The defect, as reported
-----------------------
An artist testing on 2026-08-30: *"sometimes I click a button and nothing happens,
I have to click again."* Not one button — **all of them**, intermittently, and with
**no reaction at all**: no spinner, no "Running…" indicator.

That last detail is what makes this diagnosable. A click that produces no reaction
never reached the server, so no amount of button logic could explain it. Ruled out
mechanically before looking further:

  * no `st.button` misplaced inside a `st.form` (the usual first suspect);
  * every navigation button already ends in `goto()` → `st.rerun()`;
  * the six onboarding step buttons write their state and rerun.

Streamlit talks to the browser over a websocket. Measured the same day:

    curl -I https://app.streamlytics.fr/   ->  server: cloudflare, cf-ray: …
    server.websocketPingInterval           ->  None    (no keepalive at all)

Cloudflare closes an idle websocket. With no ping, an artist who reads a page for a
couple of minutes loses the connection silently; the next click goes nowhere, and
the one after works because the browser reconnected in between. Streamlit's own
help for the option names the situation: *"if you're experiencing frequent
disconnections in certain proxy setups"*.

Why a test rather than a comment in the config
----------------------------------------------
`showErrorDetails` was *also* meant to be set and was measured at Streamlit's
default in production on 2026-08-23, sending full tracebacks to visitors' browsers.
A configuration value nobody asserts is a value that silently reverts to the default
— and this default is `None`, i.e. the broken behaviour.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_CONFIG = _ROOT / ".streamlit" / "config.toml"

# Cloudflare closes an idle websocket. The exact window is not contractual, so the
# ping has to sit comfortably under it rather than just below a remembered number.
_MAX_SAFE_INTERVAL_S = 60
_MIN_SANE_INTERVAL_S = 5


def _server_config() -> dict:
    with _CONFIG.open("rb") as fh:
        return tomllib.load(fh).get("server", {})


def test_the_websocket_ping_is_configured():
    interval = _server_config().get("websocketPingInterval")
    assert interval is not None, (
        "server.websocketPingInterval is unset, so Streamlit sends NO websocket "
        "keepalive. Behind Cloudflare that means the connection dies while an artist "
        "reads the page, and their next click does nothing at all — no spinner, no "
        "error. That is the 2026-08-30 report, and the default is exactly this."
    )
    assert _MIN_SANE_INTERVAL_S <= interval <= _MAX_SAFE_INTERVAL_S, (
        f"websocketPingInterval={interval}s is outside {_MIN_SANE_INTERVAL_S}.."
        f"{_MAX_SAFE_INTERVAL_S}s. Too long and Cloudflare closes the socket between "
        "pings; too short and every client pays a frame for nothing."
    )


def test_the_error_detail_setting_is_still_pinned():
    """The neighbouring value that DID silently revert once.

    Measured in production on 2026-08-23: `showErrorDetails` was at Streamlit's
    default `full`, rendering complete tracebacks — file paths, code, and exception
    messages this repo knows can carry a credential — into a visitor's browser. It
    lives in the same file, and it is here so that this test file is the thing that
    notices if either goes back to a default.
    """
    with _CONFIG.open("rb") as fh:
        client = tomllib.load(fh).get("client", {})
    assert client.get("showErrorDetails") == "none", (
        f"client.showErrorDetails is {client.get('showErrorDetails')!r}, not 'none'. "
        "Streamlit's default sends the full traceback to the visitor's browser."
    )


def test_the_config_is_the_one_the_container_reads():
    """A config the app never loads is a config that does nothing.

    The Dockerfile copies `.streamlit/` into the image; if that COPY ever goes, the
    file here would keep passing every assertion above while production ran on
    defaults — the shape of `config-not-env`, one directory over.
    """
    dockerfile = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert ".streamlit/" in dockerfile, (
        "Dockerfile no longer copies .streamlit/ into the image — every setting in "
        "config.toml is then inert in production, including this one."
    )
