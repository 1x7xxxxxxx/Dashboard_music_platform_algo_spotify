"""The nightly alert must say what the API answered, not what we guessed.

Installed 2026-08-22. Two surfaces answered "is this artist's platform working":

    artist_readiness  → reads the DATABASE. Knows THAT nothing arrived.
                        Guesses at why, from a static `nodata_hint`.
    CONNECTION_TESTS  → calls the platform API. Knows WHY.
                        Ran only when a human clicked or typed.

Measured divergence on GRiNCH (tenant 13), the same night:

    probe  → "User ID 72854583 joignable, mais aucun titre public n'y est rattaché"
    alert  → "vérifie le User ID ; l'app SoundCloud partagée doit être configurée (admin)"

The second is a guess, it is wrong, it blames the artist AND the admin for an account
that simply has no public tracks, and it is the one that was automatic. Two beta
sessions were spent on that gap.

The three properties below are what keep the cure from becoming the disease:
the probe runs only on reds, it never changes a status, and "not measured" never
renders as "measured and fine".
"""
from __future__ import annotations

import pytest

from src.utils.artist_readiness import (
    BROKEN, NO_DATA, OK, TODO, next_action,
)

_SOUNDCLOUD = {
    "key": "soundcloud", "label": "☁️ SoundCloud",
    "id_hint": "ton User ID SoundCloud numérique",
    "nodata_hint": "vérifie le User ID ; l'app SoundCloud partagée doit être configurée (admin)",
}
# The exact string `_platform_soundcloud._test_soundcloud` returns for GRiNCH.
_GRINCH_TRUTH = ("User ID 72854583 joignable, mais **aucun titre public** n'y est "
                 "rattaché — il n'y aura donc rien à collecter.")


# ── the pure function ────────────────────────────────────────────────────────

def test_a_live_reason_replaces_the_static_guess():
    assert next_action(_SOUNDCLOUD, NO_DATA, None, _GRINCH_TRUTH) == _GRINCH_TRUTH


def test_without_a_live_reason_the_static_hint_is_kept():
    """Non-vacuity, and the compatibility contract: no probe ⇒ today's behaviour."""
    assert next_action(_SOUNDCLOUD, NO_DATA) == _SOUNDCLOUD["nodata_hint"]


def test_a_live_reason_does_not_leak_into_other_statuses():
    """TODO means "you have not filled the field", whatever an API might say."""
    assert next_action(_SOUNDCLOUD, TODO, None, _GRINCH_TRUTH) != _GRINCH_TRUTH
    assert "Renseigne" in next_action(_SOUNDCLOUD, TODO, None, _GRINCH_TRUTH)


def test_broken_still_asks_the_artist_for_nothing():
    """BROKEN is our failure. The wording must not start blaming them."""
    msg = next_action(_SOUNDCLOUD, BROKEN, None, None)
    assert "Rien à faire de ton côté" in msg


# ── the matrix, with a fake DB and a spying probe ────────────────────────────

class _FakeDB:
    """Minimal stand-in: one declared SoundCloud identity, zero rows anywhere.

    That is exactly GRiNCH's production state — an identity the artist entered, and
    not one row in any table.
    """

    def __init__(self, identity="72854583"):
        self.identity = identity

    def fetch_df(self, sql, params=None):
        import pandas as pd
        if "artist_credentials" in sql.lower() and self.identity:
            return pd.DataFrame([{"platform": "soundcloud",
                                  "extra_config": {"user_id": self.identity}}])
        return pd.DataFrame(columns=["platform", "extra_config"])

    def fetch_query(self, sql, params=None):
        low = sql.lower()
        if "artist_credentials" in low:
            return [("soundcloud", {"user_id": self.identity})] if self.identity else []
        if "spotify_artist_id" in low:
            return [(None,)]
        # Since 2026-08-22 `check_freshness` asks Postgres for the age in the same
        # statement as the value — one clock instead of two. Two columns:
        # (MAX(col), age_hours). Nothing here has ever collected, so both are NULL.
        return [(None, None)]

    def close(self):
        pass


class _Spy:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def __call__(self, platform):
        self.calls.append(platform)
        return self.result


def _matrix(db, probe):
    from src.utils.artist_readiness import artist_readiness
    return artist_readiness(db, 13, probe=probe)


def test_the_grinch_regression(monkeypatch):
    """The whole point, as data: the alert must carry the measurement."""
    spy = _Spy((False, _GRINCH_TRUTH))
    rows = {m["key"]: m for m in _matrix(_FakeDB(), spy)}
    sc = rows["soundcloud"]

    assert sc["status"] == NO_DATA, f"fixture did not reproduce the red: {sc['status']}"
    assert _GRINCH_TRUTH in sc["next_action"], (
        f"the alert still carries the guess: {sc['next_action']!r}"
    )
    assert "l'app SoundCloud partagée" not in sc["next_action"], (
        "the static hint survived — it blames the admin for an empty account"
    )
    assert sc["probe_ran"] is True


def test_only_the_reds_are_probed():
    """Freshness is the proof; the probe is the explainer. Never probe green."""
    spy = _Spy((False, "should not be called"))
    db = _FakeDB(identity="")          # nothing declared ⇒ every platform is TODO
    _matrix(db, spy)
    assert spy.calls == [], (
        f"probes fired on non-red platforms: {spy.calls}. At 100 tenants that is "
        "500 API calls a night to learn what the database already answered."
    )


def test_a_probe_that_did_not_run_is_not_a_verdict():
    """`None` means "not measured". It must never read as "measured and fine"."""
    rows = {m["key"]: m for m in _matrix(_FakeDB(), _Spy(None))}
    sc = rows["soundcloud"]
    assert sc["probe_ran"] is False
    assert sc["next_action"] == _SOUNDCLOUD["nodata_hint"], (
        "an unmeasured platform must fall back to the static hint, not to silence"
    )


def test_a_passing_probe_leaves_the_status_alone():
    """The probe explains; it does not adjudicate.

    A green probe on a red platform is a real state — the credential works and the
    collector has not run yet — and it must stay red, or the DAG stalling becomes
    invisible.
    """
    rows = {m["key"]: m for m in _matrix(_FakeDB(), _Spy((True, "tout va bien")))}
    assert rows["soundcloud"]["status"] == NO_DATA
    assert rows["soundcloud"]["status"] != OK


def test_a_raising_probe_does_not_break_the_row():
    """One platform's probe failing must not lose the other four."""
    def _boom(_platform):
        raise RuntimeError("boom")

    from src.utils.artist_readiness import artist_readiness
    with pytest.raises(RuntimeError):
        # artist_readiness does NOT swallow it — the isolation lives one level up, in
        # the DAG's per-tenant try. Pinning that here so the responsibility stays put.
        artist_readiness(_FakeDB(), 13, probe=_boom)


def test_platform_probes_absorbs_the_exception_itself():
    """…and the seam that the DAG actually uses does absorb it, as a red reason."""
    import src.utils.platform_probes as pp

    class _Reg(dict):
        pass

    def _raising(_fields):
        raise ConnectionError("dns")

    import sys
    import types
    key = "src.dashboard.views.credentials._registry"
    mod = types.ModuleType(key)
    mod.CONNECTION_TESTS = {"soundcloud": _raising}
    # RESTORE the original, never `del`. Deleting the key evicts the real module from
    # sys.modules for the REST OF THE SESSION: the next import re-executes it from disk
    # and hands out a SECOND module object, while everything that already did
    # `from … import CONNECTION_TESTS` still holds the first. A later test that patches
    # one of the two then watches the other run — which is exactly the shape of the
    # order-dependent CI failures of 2026-08-23 (green file by file, red in a full run).
    # A test may borrow global state; it may not leave a hole where it found something.
    previous = sys.modules.get(key)
    sys.modules[key] = mod
    try:
        out = pp.probe(_FakeDB(), 13, "soundcloud")
    finally:
        if previous is not None:
            sys.modules[key] = previous
        else:
            sys.modules.pop(key, None)

    assert out is not None and out[0] is False
    assert "ConnectionError" in out[1], (
        "a probe that raised must become a red REASON naming the failure, never a "
        "crash and never a verdict about the artist"
    )


def test_the_budget_is_shared_across_tenants():
    """A per-tenant cap is not a cap. 100 tenants × 5 platforms is the number."""
    from src.utils.platform_probes import make_budgeted_probe

    budget = [2]
    db = _FakeDB()
    a = make_budgeted_probe(db, 1, budget)
    b = make_budgeted_probe(db, 2, budget)
    import src.utils.platform_probes as pp
    calls = []
    original = pp.probe
    pp.probe = lambda *args: calls.append(args) or (True, "ok")
    try:
        assert a("soundcloud") is not None
        assert b("soundcloud") is not None
        assert a("youtube") is None, "the third call was not refused — budget leaked"
        assert b("youtube") is None
    finally:
        pp.probe = original
    assert len(calls) == 2
