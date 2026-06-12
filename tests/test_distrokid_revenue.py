"""Tests for the Distributeur view's manual-entry helpers (B2 phase 1)."""
from datetime import date

from src.dashboard.views.imusician import DISTRIBUTOR_TABLES, _default_period
from src.utils.distrokid_rollup import _ROLLUP_SQL, default_fx_rate, rollup_sales_to_monthly


class _FakeDB:
    """Captures the SQL + params handed to the rollup (no real Postgres)."""

    def __init__(self, count=3):
        self.calls = []
        self._count = count

    def execute_query(self, sql, params=None):
        self.calls.append((sql, params))

    def fetch_query(self, sql, params=None):
        return [(self._count,)]


class TestFxRatePersistence:
    """Migration 059: the USD->EUR rate must be persisted, not just baked into EUR."""

    def test_rollup_sql_writes_fx_rate_column(self):
        # INSERT column list and the ON CONFLICT UPDATE must both carry fx_rate,
        # else revenue_eur stays irreversible (the P2 data-integrity bug).
        assert "fx_rate" in _ROLLUP_SQL
        assert "fx_rate = EXCLUDED.fx_rate" in _ROLLUP_SQL

    def test_rollup_passes_rate_three_times_plus_artist(self):
        # 3 %s rate placeholders (revenue calc, fx_rate col, notes string) + artist_id.
        # A param-arity regression here would crash every import.
        db = _FakeDB()
        rollup_sales_to_monthly(db, artist_id=7, fx_rate=0.85)
        sql, params = db.calls[0]
        assert params == (0.85, 0.85, 0.85, 7)

    def test_default_rate_used_when_none(self):
        db = _FakeDB()
        rollup_sales_to_monthly(db, artist_id=1, fx_rate=None)
        _, params = db.calls[0]
        assert params[:3] == (default_fx_rate(),) * 3


class TestDefaultPeriod:
    def test_mid_year_returns_previous_month(self):
        assert _default_period(date(2026, 6, 10)) == (2026, 5)

    def test_january_wraps_to_december_previous_year(self):
        assert _default_period(date(2026, 1, 3)) == (2025, 12)

    def test_december(self):
        assert _default_period(date(2025, 12, 31)) == (2025, 11)


class TestDistributorTables:
    def test_tables_are_in_sql_allowlist(self):
        from src.database.postgres_handler import validate_table
        for table in DISTRIBUTOR_TABLES.values():
            validate_table(table)  # raises ValueError if not allowlisted

    def test_expected_distributors(self):
        assert set(DISTRIBUTOR_TABLES) == {'iMusician', 'DistroKid'}
