"""The one order the three algorithmic playlists are listed in: DW → Radio → RR (R380).

Type: Utility
Uses: nothing
Triggers: nothing
Depends on: nothing — read by views, PDF charts and `src/utils/` alike
Persists in: nothing

Owner's screen review (2026-10-05): the same three playlists were listed DW · RR · Radio
in one block and RR · DW · Radio in the next. Every surface reads its order from here.
Guard: `tests/test_the_algos_are_listed_in_one_order.py`.
"""
from __future__ import annotations

ALGO_ORDER = ("DW", "RADIO", "RR")

#: The name the artist reads, per code. A lookup, not an order.
ALGO_NAMES = {"DW": "Discover Weekly", "RADIO": "Radio", "RR": "Release Radar"}


def named_algos() -> tuple[tuple[str, str], ...]:
    """`(code, display name)` in the one order."""
    return tuple((a, ALGO_NAMES[a]) for a in ALGO_ORDER)
