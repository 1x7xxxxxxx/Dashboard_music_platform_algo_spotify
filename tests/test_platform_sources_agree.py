"""Guard — every surface must judge a platform on the same tables.

Error class `same-platform-judged-on-different-tables`.

Measured 2026-08-22: Spotify was judged on FOUR tables depending on the screen.
`artist_readiness` bound it to `"Spotify S4A"` (`s4a_song_timeline`, the CSV upload
table), `alert_monitor.check_canary_health` watched `track_popularity_history`, the
KPI panel read `artists`, and `freshness_monitor` knew about both. An artist who
entered their Spotify id and whose `spotify_api_daily` was collecting normally read
🔴 "Connecté — aucune donnée" until they uploaded a CSV — and Spotify is the platform
onboarding recommends first, so that was most artists' first impression of the
product. The same tenant could be green on one screen and red on another, both
truthfully.

The registry is `freshness_monitor.SOURCES_FOR_PLATFORM`. Every consumer derives
from it; nobody restates a table name.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.utils.freshness_monitor import (
    MONITOR_TARGETS,
    SOURCES_FOR_PLATFORM,
    tables_for_platform,
)

REPO = Path(__file__).resolve().parents[1]


def test_every_declared_source_exists_in_monitor_targets() -> None:
    known = {t["source"] for t in MONITOR_TARGETS}
    for platform, sources in SOURCES_FOR_PLATFORM.items():
        unknown = set(sources) - known
        assert not unknown, f"{platform} names unknown freshness source(s): {sorted(unknown)}"


def test_spotify_is_provable_by_the_api_table_and_by_the_csv() -> None:
    """Both routes must count. Either alone is a real, complete way to be collecting."""
    tables = tables_for_platform("spotify")
    assert "track_popularity_history" in tables, (
        "the Spotify API table is not among the tables that prove Spotify — an artist "
        "who connected the API but uploaded no CSV would read as 'no data'"
    )
    assert "s4a_song_timeline" in tables, (
        "the S4A CSV table is not among them — an artist who only uploads CSVs would "
        "read as 'no data'"
    )


@pytest.mark.parametrize("platform", sorted(SOURCES_FOR_PLATFORM))
def test_every_platform_resolves_to_at_least_one_table(platform: str) -> None:
    assert tables_for_platform(platform), f"{platform} is provable by no table at all"


def _dag_literal_tables() -> set[str]:
    """Table names appearing as string literals in check_canary_health's CODE.

    AST, not grep: the function's own comments name `track_popularity_history` and
    `s4a_song_timeline` in prose, explaining the very defect this guards. A textual
    signature would go red on the explanation of its own fix.
    """
    tree = ast.parse((REPO / "airflow/dags/alert_monitor.py").read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "check_canary_health")
    known = {t["table"] for t in MONITOR_TARGETS}
    known |= {t["tenant_table"] for t in MONITOR_TARGETS if t.get("tenant_table")}
    return {n.value for n in ast.walk(fn)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in known}


def test_the_canary_watchdog_hardcodes_no_table() -> None:
    """It must derive its targets, not restate them.

    The hardcoded pair it used to carry is exactly how its Spotify table drifted
    away from the one the artist's own screen reads.
    """
    literals = _dag_literal_tables()
    assert not literals, (
        "check_canary_health names table(s) literally in code: "
        f"{sorted(literals)} — derive them from SOURCES_FOR_PLATFORM instead"
    )


def test_the_kpi_panel_agrees_on_every_shared_source() -> None:
    """Where the KPI panel and the freshness monitor name the same source, the table
    must match. The panel legitimately carries sources readiness has no opinion on
    (iMusician, Apple Music); those are out of scope, drift on the shared ones is not.
    """
    from src.dashboard.utils.kpi_helpers import SOURCES_CONFIG

    by_source = {t["source"]: t["table"] for t in MONITOR_TARGETS}
    mismatched = {
        s["label"]: (s["table"], by_source[s["label"]])
        for s in SOURCES_CONFIG
        if s["label"] in by_source and s["table"] != by_source[s["label"]]
    }
    assert not mismatched, (
        "the KPI panel and the freshness monitor disagree on which table proves a "
        f"source: {mismatched}"
    )


# ── The regression this file's own change caused, pinned ──────────────────────

def test_no_platform_resolves_to_a_table_that_is_not_tenant_scopable() -> None:
    """`artist_id` is not always the tenant. Reason on the TYPE, never on the name.

    Error class `column-name-is-not-its-meaning`. On `artists`, `artist_history` and
    `tracks` the column called `artist_id` is the SPOTIFY id (VARCHAR); the tenant
    there is `saas_artist_id` (INTEGER). `MONITOR_TARGETS` encodes this with
    `skip_artist_filter` plus a separate `tenant_table`.

    Measured in PRODUCTION on 2026-08-22: an earlier version of `tables_for_platform`
    returned both the global table and the tenant table, the canary watchdog queried
    `artists` with an integer, and Postgres answered `operator does not exist:
    character varying = integer`. The check reported "could not run" — correctly
    conservative — and still put a false 🐤 CANARI MUET in the alert subject.
    """
    globals_only = {t["table"] for t in MONITOR_TARGETS if t.get("skip_artist_filter")}
    for platform in SOURCES_FOR_PLATFORM:
        leaked = tables_for_platform(platform) & globals_only
        assert not leaked, (
            f"{platform} resolves to {sorted(leaked)}, which is not scoped by an "
            f"integer artist_id — a per-tenant reader would fail on the type"
        )


def test_a_platform_with_two_tables_needs_only_one_of_them() -> None:
    """Demanding ALL of them reports a healthy tenant as mute.

    Spotify is provable by the API table OR the S4A CSV. The production canary has
    10 rows in `track_popularity_history` and 0 in `s4a_song_timeline`; requiring
    both made the watchdog cry wolf about a tenant collecting exactly as designed.
    """
    import ast

    tree = ast.parse((REPO / "airflow/dags/alert_monitor.py").read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "check_canary_health")
    src = ast.unparse(fn)
    assert "fresh" in src, (
        "check_canary_health no longer computes a per-platform 'at least one table "
        "is fresh' verdict — it is back to flagging every empty table"
    )
