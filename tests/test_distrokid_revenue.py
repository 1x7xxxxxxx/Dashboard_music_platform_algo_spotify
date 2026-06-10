"""Tests for the Distributeur view's manual-entry helpers (B2 phase 1)."""
from datetime import date

from src.dashboard.views.imusician import DISTRIBUTOR_TABLES, _default_period


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
