"""Guard: the retry-backoff shortcut must not become a global `time.sleep` patch.

Type: Utility
Uses: time, src.utils.retry
Triggers: pytest
Persists in: nothing

Error class `boundary-wider-than-its-docstring`.

Measured 2026-08-28. `conftest._retry_backoff_costs_no_wall_clock` was added to stop
paying the retry backoff in wall-clock time — eleven tests at exactly 6.00 s each
(2.0 + 4.0), 66 s of a 275 s suite spent asleep. Its first version did:

    monkeypatch.setattr(_retry.time, "sleep", lambda _s: None)

`retry.py` does `import time`, so `_retry.time` **is** the global `time` module. The
fixture therefore neutered every `sleep` in the process, and its own docstring claimed
the opposite in the same breath. The suite went from 275 s to **608 s** and the two
slowest tests turned RED: Streamlit `AppTest` and WeasyPrint waits returned instantly
and read a page that had not finished rendering.

Substituting the module REFERENCE in the consumer's namespace is what actually scopes
it. This file pins both halves, because only one of them was ever wrong: the shortcut
must work, AND the rest of the process must still be able to wait.
"""
from __future__ import annotations

import time

import pytest

retry_mod = pytest.importorskip("src.utils.retry")


def test_the_global_sleep_is_untouched():
    """A test that needs to wait must still be able to.

    This is the half the first version broke. `time.sleep` is a builtin; if the
    fixture reached the shared module, this identity no longer holds.
    """
    import time as freshly_imported
    assert freshly_imported.sleep is time.sleep
    assert getattr(time.sleep, "__module__", "time") == "time", (
        "something replaced the process-wide time.sleep. A fixture that shortcuts one "
        "module's backoff must substitute the reference in THAT module's namespace, "
        "never an attribute of the shared `time` module."
    )


def test_the_retry_module_does_not_wait():
    """And the half that must work: the backoff costs no wall clock."""
    calls = []

    @retry_mod.retry(max_attempts=3, base_delay=2.0)
    def always_fails():
        calls.append(1)
        raise ConnectionError("nope")

    started = time.monotonic()
    with pytest.raises(ConnectionError):
        always_fails()
    elapsed = time.monotonic() - started

    assert len(calls) == 3, "the retry must still retry — only the waiting is skipped"
    assert elapsed < 1.0, (
        f"three attempts took {elapsed:.2f}s. Un-shortcut, this decorator sleeps "
        "2.0 + 4.0 = 6.00s — the exact figure that made eleven collector tests cost "
        "66s of suite time."
    )


def test_a_real_short_sleep_still_sleeps():
    """Non-vacuity, from the other side: prove the clock is real here.

    Without this, a frozen or mocked clock would satisfy the test above for the wrong
    reason, and the boundary check would be measuring nothing.
    """
    started = time.monotonic()
    time.sleep(0.05)
    assert time.monotonic() - started >= 0.03, (
        "a real 50 ms sleep did not advance the clock — time itself is patched, so "
        "neither assertion in this file means anything"
    )
