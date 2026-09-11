"""The series cache memorises answers, never failures.

Type: Test
Uses: platform_timeseries, series_cache (no database — a fake handle)
Depends on: src/dashboard/utils/series_cache.py, src/dashboard/utils/platform_timeseries.py
Persists in: nothing

Why this exists
---------------
A `code-critic` review refused the first caching design on 2026-09-11, and this
was the blocking reason. The public functions of `platform_timeseries` are
written to **never raise** — `_rows`: *« Ne lève jamais : ces courbes sont un
affichage, pas un calcul de facturation »* — so on a database failure they
return empty, indistinguishable from "nothing to read".

Wrapping THOSE in `@st.cache_data` would memorise the failure. A one-second
blip would become "no data" for 600 s, for every viewer at once, on the defect
class this repository pays the most for: a failed read disguised as an absence
(`.claude/rules/python.md` — *« Une lecture qui échoue ne se déguise pas en
"rien à lire" »*).

The design that survived puts the cache **inside** the swallow, at the query:
`platform_timeseries.set_fetch()` installs it, so a raising read is never
memorised, the module's own `except` degrades exactly as before, and the next
render retries.

These tests are the proof of that property, and the reason it may not be
"simplified" later into a decorator on the public functions.

No database: a fake handle counts calls and can be told to fail. The property
under test is about caching, not about SQL.
"""
from __future__ import annotations

import pytest


class _FakeDB:
    """Counts real reads, and can be told to fail on demand."""

    def __init__(self) -> None:
        self.calls = 0
        self.failing = False

    def fetch_query(self, sql, params):  # noqa: ANN001
        self.calls += 1
        if self.failing:
            raise RuntimeError("database unreachable")
        return [("2026-01-01", 5)]


_SQL = "SELECT 1 WHERE %s = %s"


@pytest.fixture
def wired():
    """Install the cache, and always uninstall + empty it afterwards.

    A cache left installed leaks into every later test in the process, and an
    entry left behind makes the next test's call count wrong.
    """
    from src.dashboard.utils import platform_timeseries as pt
    from src.dashboard.utils import series_cache

    series_cache.clear()
    series_cache.install()
    try:
        yield pt, series_cache
    finally:
        series_cache.clear()
        pt.set_fetch(None)


def test_the_same_read_is_performed_once(wired) -> None:
    pt, _ = wired
    db = _FakeDB()
    results = [pt._rows(db, _SQL, (1, 1)) for _ in range(3)]
    assert db.calls == 1, f"{db.calls} real reads for 3 identical calls — nothing cached"
    assert results[0] == results[1] == results[2] == [("2026-01-01", 5)]


def test_a_different_tenant_is_not_served_the_first_one_s_answer(wired) -> None:
    """The key is `(sql, params)`, and every query in the module is tenant-scoped.

    Isolation is therefore structural: it does not depend on remembering to put
    the tenant in a key, which is how this kind of cache leaks.
    """
    pt, _ = wired
    db = _FakeDB()
    pt._rows(db, _SQL, (1, 1))
    pt._rows(db, _SQL, (2, 2))
    assert db.calls == 2, "two different tenants shared one cache entry"


def test_a_failure_is_not_memorised_and_the_next_render_retries(wired) -> None:
    """THE blocking point of the review. If this ever goes green by caching the
    empty result, the cache has become a ten-minute outage amplifier."""
    pt, _ = wired
    db = _FakeDB()

    db.failing = True
    degraded = pt._rows(db, _SQL, (1, 1))
    assert degraded == [], "the module stopped degrading — a view will now crash"
    assert db.calls == 1

    db.failing = False
    recovered = pt._rows(db, _SQL, (1, 1))
    assert recovered == [("2026-01-01", 5)], (
        "the FAILURE was cached: after the database came back, the page still shows "
        "'no data'. This is the defect the caching design was refused for."
    )
    assert db.calls == 2, "the retry never reached the database"


def test_clearing_forces_the_next_read_to_go_out(wired) -> None:
    """Without this, the 600 s TTL is the only invalidation, and the five events
    that change data mid-day would be unable to refresh anything."""
    pt, cache = wired
    db = _FakeDB()
    pt._rows(db, _SQL, (1, 1))
    cache.clear()
    pt._rows(db, _SQL, (1, 1))
    assert db.calls == 2, "clear() did not empty the cache"


def test_clear_kpi_caches_also_empties_the_series_cache(wired) -> None:
    """The two caches cover the same tables and must expire together.

    `clear_kpi_caches()` is wired at the five sites that change data during the
    day; if it emptied only half of what it serves, a CSV re-upload would
    refresh the tiles and leave the curve stale — a screen disagreeing with
    itself, which reads as a data bug.
    """
    pt, _ = wired
    from src.dashboard.utils.kpi_helpers import clear_kpi_caches

    db = _FakeDB()
    pt._rows(db, _SQL, (1, 1))
    clear_kpi_caches()
    pt._rows(db, _SQL, (1, 1))
    assert db.calls == 2, (
        "clear_kpi_caches() left the series cache populated — the tiles refresh and "
        "the curve does not."
    )
