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

    "Connected" means an IDENTITY was declared, not that a row exists. `set(rows)`
    counted a tab the artist opened and saved blank, and it counted the meta row as
    Meta-connected when it held only `ig_user_id`. Both read as ✅ on the KPI strip
    while the readiness matrix said ⚪ — two surfaces, same data, opposite answers.

    Instagram has no row of its own: it rides the `meta` row through `ig_user_id`.
    The registry knows that, so this no longer restates it.
    """
    import json

    from src.utils.tenant_identity import declared_identities

    extra_by_platform = {}
    for platform, row in (rows or {}).items():
        extra = (row or {}).get("extra_config") or {}
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except ValueError:
                extra = {}
        extra_by_platform[platform] = extra if isinstance(extra, dict) else {}
    return declared_identities(extra_by_platform)


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
