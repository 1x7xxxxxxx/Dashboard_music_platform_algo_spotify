"""A cached read is keyed on a value that stays equal for the life of the cache.

Type: Sub
Uses: src/dashboard/utils/live_pulse.py
Depends on: nothing — the cached function is replaced by a recorder
Persists in: nothing

Class `a-cache-key-that-can-never-be-hit-twice`. `get_live_pulse` passed
`cutoff = now() - 5 min` straight into its cached helper: two renders a millisecond apart
produced two keys, so the cache never hit. The class named
`tests/test_a_page_asks_the_same_question_once.py` as its guard, and on 2026-09-26 removing
the rounding left that file GREEN — it clears every cache between renders and never
reaches the pulse. This guard asks the property directly: two calls inside one TTL window
hand the cached helper the SAME key.
"""
from __future__ import annotations

import datetime as dt

import src.dashboard.utils.live_pulse as lp


def _keys_of_two_calls(monkeypatch, first: dt.datetime, second: dt.datetime) -> list:
    seen: list = []
    monkeypatch.setattr(lp, "_pulse_counts", lambda _db, cutoff: seen.append(cutoff) or (0, 0))
    clock = iter([first, second])

    class _Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001, ANN206
            return next(clock)

    monkeypatch.setattr(lp, "datetime", _Clock)
    lp.get_live_pulse(None)
    lp.get_live_pulse(None)
    return seen


def test_two_calls_inside_one_window_share_one_key(monkeypatch) -> None:
    t0 = dt.datetime(2026, 9, 26, 12, 0, 3, 120_000, tzinfo=dt.timezone.utc)
    keys = _keys_of_two_calls(monkeypatch, t0, t0 + dt.timedelta(milliseconds=7))
    assert keys[0] == keys[1], (
        f"two renders 7 ms apart asked the cache with {keys} — a key that changes on "
        "every call is a cache that never hits")


def test_the_key_still_moves_across_windows(monkeypatch) -> None:
    """Non-vacuity, the other half: a key frozen forever would pass the test above and
    serve a stale count for good."""
    t0 = dt.datetime(2026, 9, 26, 12, 0, 3, tzinfo=dt.timezone.utc)
    keys = _keys_of_two_calls(monkeypatch, t0, t0 + dt.timedelta(seconds=lp._PULSE_TTL_S))
    assert keys[0] != keys[1]
