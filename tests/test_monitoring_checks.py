"""Tests for the pure alert_monitor detectors (src/utils/monitoring_checks.py).

Guards the three silent failure modes the Benken week exposed: DAGs failing every day
(masked by a 7-day total count), collectors succeeding with 0 rows per tenant, and a
per-tenant freshness gap masked by global freshness.
"""
from datetime import date, datetime

from src.utils.monitoring_checks import (
    consecutive_failure_days,
    silent_zero_findings,
    tenant_freshness_gaps,
)


# ── consecutive_failure_days ──────────────────────────────────────────────────

def _runs(dag, *day_states):
    """day_states: (day_int, state) → (dag, date(2026,6,day), state)."""
    return [(dag, date(2026, 6, d), s) for d, s in day_states]


def test_flags_three_consecutive_failed_days():
    runs = _runs("youtube_daily", (16, "failed"), (17, "failed"), (18, "failed"))
    assert consecutive_failure_days(runs) == {"youtube_daily": 3}


def test_two_failures_do_not_escalate():
    runs = _runs("soundcloud_daily", (17, "failed"), (18, "failed"))
    assert consecutive_failure_days(runs, min_days=3) == {}


def test_streak_breaks_on_a_success_day():
    # latest day succeeded → streak ends at 0 even if earlier days failed
    runs = _runs("youtube_daily", (16, "failed"), (17, "failed"), (18, "success"))
    assert consecutive_failure_days(runs) == {}


def test_streak_breaks_on_a_missing_day():
    runs = _runs("youtube_daily", (16, "failed"), (18, "failed"), (19, "failed"))
    # 18-19 = only 2 consecutive (17 missing) → no escalation at min_days=3
    assert consecutive_failure_days(runs, min_days=3) == {}


def test_accepts_datetime_exec_dates():
    runs = [("d", datetime(2026, 6, 18, 10, 0), "failed"),
            ("d", datetime(2026, 6, 17, 10, 0), "failed"),
            ("d", datetime(2026, 6, 16, 10, 0), "failed")]
    assert consecutive_failure_days(runs) == {"d": 3}


# ── silent_zero_findings ──────────────────────────────────────────────────────

def test_flags_configured_zero_row_tenant():
    rows = [
        (12, "Benken", "soundcloud", True, 0),    # configured, no data → flag
        (12, "Benken", "youtube", True, 7),       # has data → ok
        (12, "Benken", "meta", False, 0),         # not configured → ignore
        (1, "Admin", "spotify", True, 120),       # ok
    ]
    out = silent_zero_findings(rows)
    assert out == [{"artist_id": 12, "artist_name": "Benken", "platform": "soundcloud"}]


def test_none_row_count_treated_as_zero():
    assert silent_zero_findings([(5, "X", "youtube", True, None)]) == [
        {"artist_id": 5, "artist_name": "X", "platform": "youtube"}
    ]


# ── tenant_freshness_gaps ─────────────────────────────────────────────────────

def test_per_tenant_stale_sources_isolated():
    per_tenant = [
        (1, "Admin", [{"source": "Spotify", "stale": False}]),
        (12, "Benken", [{"source": "SoundCloud", "stale": True},
                        {"source": "YouTube", "stale": True},
                        {"source": "Apple", "stale": False}]),
    ]
    out = tenant_freshness_gaps(per_tenant)
    assert out == [{"artist_id": 12, "artist_name": "Benken",
                    "stale_sources": ["SoundCloud", "YouTube"]}]


def test_no_gaps_when_all_fresh():
    per_tenant = [(1, "Admin", [{"source": "Spotify", "stale": False}])]
    assert tenant_freshness_gaps(per_tenant) == []
