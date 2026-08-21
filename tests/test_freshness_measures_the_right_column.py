"""Freshness must measure the day the data DESCRIBES, not the day it was written.

Installed 2026-08-21, from a production measurement:

    meta_insights_performance_day
        MAX(collected_at) = that morning, 07:01
        MAX(day_date)     = 2024-09-30
        rows with day_date in the last 7 days = 0

The DAG was running. It re-upserted the same two-year-old rows every night, so the
write timestamp advanced forever — and all seven freshness probes read the write
timestamp. Meta Ads had collected nothing since early August and every light was
green. After the fix the same probe reports **16 577 hours stale**.

This is the "green light that lies" class this repo keeps meeting: the SoundCloud
connection test passing on 0 public tracks, readiness showing ⚪ while the tenant
leak ran, `psql` exiting 0 after an error. Each time the measurement and the
question were about different things.

Two properties are pinned:

  * a monitored table that HAS a distinct metric-date column must declare it —
    otherwise the same silence comes back on the next table that grows one;
  * a table that has none must NOT declare one, so nobody "fixes" a snapshot
    table (followers today, tracks today) where the write time IS the measurement.

The first check is DB-gated because only the live schema knows which tables carry
a metric date. The rest is static and runs everywhere.
"""
from __future__ import annotations

import pytest

from src.utils.freshness_monitor import MONITOR_TARGETS
from tests.db_gate import requires_live_db

# Column names that mean "the day this row is about", as opposed to when it landed.
_METRIC_NAMES = ("day_date", "date", "day", "metric_date", "report_date")


def test_every_declared_metric_column_is_named_like_one():
    """A typo here silently falls back to the write timestamp."""
    for target in MONITOR_TARGETS:
        for key in ("metric_col", "tenant_metric_col"):
            col = target.get(key)
            if col:
                assert col in _METRIC_NAMES, (
                    f"{target['source']}: {key}={col!r} is not a recognised metric-date "
                    "name. If it is one, add it to _METRIC_NAMES here; if it is a typo, "
                    "freshness has quietly gone back to measuring the write time."
                )


def test_the_result_says_which_column_answered():
    """'Fresh' means two different things; a reader has to know which."""
    import inspect

    from src.utils import freshness_monitor

    src = inspect.getsource(freshness_monitor.check_freshness)
    assert '"measured_on"' in src, (
        "check_freshness no longer reports `measured_on`. Without it, "
        "'written recently' and 'describes a recent day' are indistinguishable "
        "downstream — which is exactly how Meta Ads stayed green for two years."
    )


def test_meta_ads_is_measured_on_its_metric_date():
    """The specific regression, named where someone will look for it."""
    meta = next((t for t in MONITOR_TARGETS if t["source"] == "Meta Ads"), None)
    assert meta, "Meta Ads left MONITOR_TARGETS"
    assert meta.get("metric_col") == "day_date", (
        "Meta Ads is measured on its write timestamp again. The collector "
        "re-upserts old rows, so that timestamp advances nightly whether or not "
        "any new advertising day arrives."
    )


@requires_live_db()
def test_no_monitored_table_hides_a_metric_date():
    """The general form: only the live schema knows which tables grew one."""
    from src.dashboard.utils import get_db_connection

    db = get_db_connection()
    try:
        missing = []
        for target in MONITOR_TARGETS:
            for table_key, col_key in (("table", "metric_col"),
                                       ("tenant_table", "tenant_metric_col")):
                table = target.get(table_key)
                if not table:
                    continue
                rows = db.fetch_query(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = %s AND column_name = ANY(%s)",
                    (table, list(_METRIC_NAMES)))
                present = {r[0] for r in (rows or [])}
                if present and not target.get(col_key):
                    missing.append(
                        f"{target['source']} → {table} carries {sorted(present)} "
                        f"but declares no {col_key}")
        assert not missing, (
            "a monitored table records the day its data is about, and freshness is "
            "reading the write timestamp instead:\n  " + "\n  ".join(missing)
            + "\n\nA collector that re-writes old rows keeps that timestamp moving "
              "forever — the table looks fresh and the data is not."
        )
    finally:
        db.close()


@requires_live_db()
def test_no_snapshot_table_declares_a_metric_date_it_does_not_have():
    """The symmetric error: measuring a column that is not there fails the check.

    `check_freshness` catches its own exception and reports `error`, so this would
    not crash — it would render as a permanent red light on a healthy source, which
    is the other way to make a monitor unreadable.
    """
    from src.dashboard.utils import get_db_connection

    db = get_db_connection()
    try:
        phantom = []
        for target in MONITOR_TARGETS:
            for table_key, col_key in (("table", "metric_col"),
                                       ("tenant_table", "tenant_metric_col")):
                table, col = target.get(table_key), target.get(col_key)
                if not (table and col):
                    continue
                rows = db.fetch_query(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = %s AND column_name = %s", (table, col))
                if not rows:
                    phantom.append(f"{target['source']} → {table}.{col} does not exist")
        assert not phantom, "\n  ".join(["declared metric column is absent:"] + phantom)
    finally:
        db.close()


def test_the_allowlist_covers_the_metric_columns():
    """Rule #8: an interpolated identifier is validated before it reaches SQL."""
    from src.utils.freshness_monitor import _ALLOWED_COLS

    for target in MONITOR_TARGETS:
        for key in ("metric_col", "tenant_metric_col"):
            col = target.get(key)
            if col:
                assert col in _ALLOWED_COLS, (
                    f"{col!r} is interpolated into the freshness query but is not in "
                    "_ALLOWED_COLS — the allowlist that stands between this f-string "
                    "and identifier injection."
                )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
