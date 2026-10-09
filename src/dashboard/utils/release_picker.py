"""
Type: Utility
Uses: streamlit
Depends on: nothing (the caller passes its options, newest release first)
Persists in: st.session_state (the widget's own key)
Triggers: rendered inside a view's show(); reruns on widget change

THE release selector shared by every comparison in the app (R478, owner W7/W11,
2026-10-09 : « mêmes filtres cohérents dans toute l'app », « d'office les deux
dernières sorties »).

Before R478 the rule « the two latest releases » lived at three call sites, each
with its own widget : a multiselect `titles[:2]` (SoundCloud), another `labels[:2]`
(Spotify for Artists), and two side-by-side selectboxes (Apple Music) — the same
question asked three ways. The period answers the OTHER half of the rule
(`period_filter`, whole history by default) ; this answers which titles.

The caller orders its options newest release first : the default is the head of
that list, so the ordering — not this module — decides what « latest » means.
"""
from __future__ import annotations

from typing import Callable, Optional, Sequence

import streamlit as st

LATEST_RELEASES = 2


def default_releases(options: Sequence, n: int = LATEST_RELEASES) -> list:
    """The n latest releases, given options ordered newest first. Pure."""
    return list(options[:n])


def release_picker(
    label: str,
    options: Sequence,
    *,
    key: str,
    n: int = LATEST_RELEASES,
    format_func: Optional[Callable] = None,
    container=None,
    **widget_kwargs,
) -> list:
    """Render the shared multiselect — the n latest releases preselected."""
    where = container if container is not None else st
    if format_func is not None:
        widget_kwargs["format_func"] = format_func
    return where.multiselect(label, list(options), default=default_releases(options, n),
                             key=key, **widget_kwargs)
