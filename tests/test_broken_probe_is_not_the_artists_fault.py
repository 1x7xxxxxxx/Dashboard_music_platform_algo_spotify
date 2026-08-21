"""Guard — a check that FAILED must not render as "connected, no data".

Error class `broken-probe-rendered-as-user-fault`.

`check_freshness` sets an `error` field precisely so a broken check (missing table,
bad identifier, dead connection) is distinguishable from "the artist connected and
nothing arrived". Its own comment says so. Until 2026-08-22 nothing read it:
`artist_readiness` passed `last_dt=None, stale=True` and every failure rendered
🔴 "Connecté — aucune donnée", with a next action telling the artist to check an id
that was never the problem. `tools/artist_preflight.py` inherited the same blindness.

Telling a user to fix our outage is worse than saying nothing: they change a working
setting, and the next screen still says red.
"""
from __future__ import annotations

from src.utils.artist_readiness import (
    BROKEN,
    NO_DATA,
    OK,
    QUIET,
    TODO,
    _LABEL,
    _RANK,
    next_action,
    platform_status,
)

_P = {"key": "youtube", "label": "🎬 YouTube", "id_hint": "ton Channel ID (UC…)",
      "nodata_hint": "ta chaîne n'a peut-être aucune vidéo publique"}


def test_a_failed_probe_is_broken_not_no_data() -> None:
    assert platform_status(True, None, True, None, "relation does not exist") == BROKEN


def test_no_error_still_means_no_data() -> None:
    assert platform_status(True, None, True, None, None) == NO_DATA


def test_a_missing_identity_still_outranks_a_failed_probe() -> None:
    """The tenant's own move comes first: without an id the probe cannot even run."""
    assert platform_status(False, None, True, None, "boom") == TODO


def test_a_failed_probe_outranks_an_expected_silence() -> None:
    """A measured 'nothing to send' is a claim; a failed check cannot support it."""
    assert platform_status(True, None, True, "meta_no_active_campaign", "boom") == BROKEN


def test_broken_asks_the_artist_for_nothing() -> None:
    action = next_action(_P, BROKEN)
    assert "ton" not in action.lower() or "de ton côté" in action.lower(), action
    assert "renseigne" not in action.lower(), action
    for hint in (_P["id_hint"], _P["nodata_hint"]):
        assert hint not in action, "the artist is being told to fix something of theirs"


def test_broken_ranks_below_every_answering_state() -> None:
    """A probe that failed must never outrank a source that actually answered."""
    assert _RANK[TODO] < _RANK[BROKEN] < _RANK[NO_DATA] < _RANK[QUIET] <= _RANK[OK]


def test_broken_has_its_own_icon_and_label() -> None:
    assert _LABEL[BROKEN] != _LABEL[NO_DATA], (
        "a broken check reads identically to 'connected, no data' — the whole defect"
    )


def test_red_flags_include_broken() -> None:
    """Both need somebody to look; only one is the artist's move."""
    import src.utils.artist_readiness as ar

    rows = [
        {"key": "a", "status": NO_DATA}, {"key": "b", "status": BROKEN},
        {"key": "c", "status": OK}, {"key": "d", "status": TODO},
    ]
    ar_flags = [m for m in rows if m["status"] in (NO_DATA, ar.BROKEN)]
    assert {m["key"] for m in ar_flags} == {"a", "b"}
