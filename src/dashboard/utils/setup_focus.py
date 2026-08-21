"""The platforms the artist chose to set up first, carried across pages.

Type: Utility
Uses: streamlit session_state only
Depends on: src.dashboard.content.platform_value
Persists in: st.session_state['_setup_focus'] (per-session; a deliberate
    non-persistence — a choice made in onboarding is a plan for the next ten
    minutes, not an account setting)

The onboarding focus picker writes it; the credentials page reads it to show
what is left of that plan instead of six equal tabs. Pure helpers here so the
progress logic is testable without Streamlit.
"""
from __future__ import annotations

FOCUS_KEY = "_setup_focus"


def connected_platforms(rows: dict) -> set[str]:
    """Connected platform keys from {platform: row} of artist_credentials.

    Instagram has no row of its own: it rides the `meta` row through
    `ig_user_id` (the convention artist_readiness._identity already uses).
    Counting rows alone leaves Instagram permanently unconnected — which, next
    to a ⭐ recommending it, reads as the product being broken.
    """
    import json

    connected = set(rows or {})
    meta = (rows or {}).get("meta") or {}
    extra = meta.get("extra_config") or {}
    if isinstance(extra, str):
        try:
            extra = json.loads(extra)
        except ValueError:
            extra = {}
    if isinstance(extra, dict) and extra.get("ig_user_id"):
        connected.add("instagram")
    return connected


def remaining(focus: list[str] | None, connected: set[str]) -> list[str]:
    """Selected platforms still not connected, in the order they were chosen."""
    return [k for k in (focus or []) if k not in connected]


def progress(focus: list[str] | None, connected: set[str]) -> tuple[int, int]:
    """(done, total) over the artist's own selection — not over all platforms.

    Progress against a plan the artist did not make ("2/6 platforms") reads as
    failure; progress against their own two reads as almost-done.
    """
    focus = focus or []
    return sum(1 for k in focus if k in connected), len(focus)


def get_focus() -> list[str]:
    import streamlit as st

    value = st.session_state.get(FOCUS_KEY) or []
    return [k for k in value if isinstance(k, str)]


def clear_focus() -> None:
    import streamlit as st

    st.session_state.pop(FOCUS_KEY, None)
