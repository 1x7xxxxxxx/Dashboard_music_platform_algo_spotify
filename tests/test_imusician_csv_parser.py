"""Unit tests — IMusicianCSVParser (release_summary + sales_detail)."""
import pytest
import pandas as pd
from pathlib import Path

from src.transformers.imusician_csv_parser import IMusicianCSVParser


ARTIST_ID = 42
parser = IMusicianCSVParser()


# =============================================================================
# detect_csv_type
# =============================================================================

class TestDetectCSVType:
    def test_detects_release_summary(self):
        df = pd.DataFrame({
            "Release title": ["Album A"],
            "Track streams": [1000],
            "Total revenue": [12.50],
            "Statement date": ["2024-01"],
        })
        assert parser.detect_csv_type(df) == "release_summary"

    def test_detects_sales_detail(self):
        df = pd.DataFrame({
            "Sales date": ["2024-01"],
            "ISRC": ["FR1234567890"],
            "Shop": ["Spotify"],
        })
        assert parser.detect_csv_type(df) == "sales_detail"

    def test_returns_none_for_unknown(self):
        df = pd.DataFrame({"foo": [1], "bar": [2]})
        assert parser.detect_csv_type(df) is None

    def test_sales_date_prevents_release_summary(self):
        # Has all release_summary cols BUT also has Sales date → sales_detail wins
        df = pd.DataFrame({
            "Release title": ["X"],
            "Track streams": [1],
            "Total revenue": [1.0],
            "Sales date": ["2024-01"],
            "ISRC": ["FR123"],
            "Shop": ["Deezer"],
        })
        assert parser.detect_csv_type(df) == "sales_detail"

    def test_column_names_case_insensitive(self):
        df = pd.DataFrame({
            "RELEASE TITLE": ["X"],
            "TRACK STREAMS": [1],
            "TOTAL REVENUE": [1.0],
            "Statement Date": ["2024-01"],
        })
        assert parser.detect_csv_type(df) == "release_summary"


# =============================================================================
# _parse_yyyymm
# =============================================================================

class TestParseYYYYMM:
    def test_valid_date(self):
        assert parser._parse_yyyymm("2024-03") == (2024, 3)

    def test_extra_day_part_ignored(self):
        assert parser._parse_yyyymm("2024-03-15") == (2024, 3)

    def test_nan_raises(self):
        with pytest.raises(ValueError):
            parser._parse_yyyymm(float("nan"))

    def test_no_separator_raises(self):
        with pytest.raises(ValueError):
            parser._parse_yyyymm("202403")


# =============================================================================
# _clean_numeric
# =============================================================================

class TestCleanNumeric:
    def test_float_value(self):
        assert parser._clean_numeric("12.50") == 12.50

    def test_comma_decimal(self):
        assert parser._clean_numeric("12,50") == 12.50

    def test_int_dtype(self):
        assert parser._clean_numeric("100", int) == 100

    def test_nan_returns_zero(self):
        assert parser._clean_numeric(float("nan")) == 0.0

    def test_invalid_string_returns_zero(self):
        assert parser._clean_numeric("N/A") == 0.0


# =============================================================================
# _col
# =============================================================================

class TestCol:
    def test_exact_match(self):
        df = pd.DataFrame({"Release title": [], "ISRC": []})
        assert parser._col(df, "Release title") == "Release title"

    def test_case_insensitive(self):
        df = pd.DataFrame({"RELEASE TITLE": []})
        assert parser._col(df, "release title") == "RELEASE TITLE"

    def test_missing_returns_none(self):
        df = pd.DataFrame({"foo": []})
        assert parser._col(df, "release title") is None


# =============================================================================
# parse_release_summary
# =============================================================================

class TestParseReleaseSummary:
    def _make_df(self, rows):
        return pd.DataFrame(rows)

    def test_single_valid_row(self):
        df = self._make_df([{
            "Statement date": "2024-01",
            "Release title": "My Album",
            "Barcode": "1234567890",
            "Track downloads": 10,
            "Track streams": 5000,
            "Release downloads": 0,
            "Track downloads revenue": 1.50,
            "Track streams revenue": 20.00,
            "Release downloads revenue": 0.0,
            "Total revenue": 21.50,
        }])
        result = parser.parse_release_summary(df, ARTIST_ID)
        assert len(result) == 1
        r = result[0]
        assert r["artist_id"] == ARTIST_ID
        assert r["year"] == 2024
        assert r["month"] == 1
        assert r["release_title"] == "My Album"
        assert r["track_streams"] == 5000
        assert r["total_revenue"] == 21.50

    def test_skips_row_with_invalid_date(self):
        df = self._make_df([
            {"Statement date": "bad-date", "Release title": "X", "Total revenue": 1.0},
            {"Statement date": "2024-02", "Release title": "Y", "Total revenue": 2.0,
             "Track streams": 100},
        ])
        result = parser.parse_release_summary(df, ARTIST_ID)
        assert len(result) == 1
        assert result[0]["release_title"] == "Y"

    def test_empty_numeric_defaults_to_zero(self):
        df = self._make_df([{
            "Statement date": "2024-03",
            "Release title": "Z",
            "Track streams": None,
            "Total revenue": None,
        }])
        result = parser.parse_release_summary(df, ARTIST_ID)
        assert result[0]["track_streams"] == 0
        assert result[0]["total_revenue"] == 0.0

    def test_all_null_rows_dropped(self):
        df = pd.DataFrame([{col: None for col in [
            "Statement date", "Release title", "Track streams", "Total revenue"
        ]}])
        result = parser.parse_release_summary(df, ARTIST_ID)
        assert result == []


# =============================================================================
# parse_sales_detail
# =============================================================================

class TestParseSalesDetail:
    def _make_df(self, rows):
        return pd.DataFrame(rows)

    def _base_row(self, **overrides):
        row = {
            "Sales date": "2024-01",
            "Statement date": "2024-02",
            "ISRC": "FR1234567890",
            "Shop": "Spotify",
            "Country": "FR",
            "Transaction type": "stream",
            "Release title": "My Album",
            "Quantity": 100,
            "Revenue EUR": 5.00,
        }
        row.update(overrides)
        return row

    def test_single_valid_row(self):
        df = self._make_df([self._base_row()])
        result = parser.parse_sales_detail(df, ARTIST_ID)
        assert len(result) == 1
        r = result[0]
        assert r["artist_id"] == ARTIST_ID
        assert r["sales_year"] == 2024
        assert r["sales_month"] == 1
        assert r["isrc"] == "FR1234567890"
        assert r["shop"] == "Spotify"
        assert r["quantity"] == 100
        assert r["revenue_eur"] == 5.00

    def test_deduplication_aggregates_quantity_and_revenue(self):
        """Two rows with same conflict key → aggregated into one."""
        df = self._make_df([
            self._base_row(Quantity=50, **{"Revenue EUR": 2.50}),
            self._base_row(Quantity=30, **{"Revenue EUR": 1.50}),
        ])
        result = parser.parse_sales_detail(df, ARTIST_ID)
        assert len(result) == 1
        assert result[0]["quantity"] == 80
        assert abs(result[0]["revenue_eur"] - 4.00) < 0.001

    def test_different_countries_not_deduped(self):
        df = self._make_df([
            self._base_row(Country="FR"),
            self._base_row(Country="DE"),
        ])
        result = parser.parse_sales_detail(df, ARTIST_ID)
        assert len(result) == 2

    def test_skips_row_with_invalid_date(self):
        df = self._make_df([
            self._base_row(**{"Sales date": "bad"}),
            self._base_row(ISRC="FR9999999999", Country="BE"),
        ])
        result = parser.parse_sales_detail(df, ARTIST_ID)
        assert len(result) == 1
        assert result[0]["isrc"] == "FR9999999999"


# =============================================================================
# parse_csv_file
# =============================================================================

class TestParseCSVFile:
    def test_release_summary_file(self, tmp_path):
        csv = (
            "Statement date,Release title,Barcode,Track downloads,Track streams,"
            "Release downloads,Track downloads revenue,Track streams revenue,"
            "Release downloads revenue,Total revenue\n"
            "2024-01,My Album,123456,0,5000,0,0.0,20.0,0.0,20.0\n"
        )
        path = tmp_path / "release_summary.csv"
        path.write_text(csv, encoding="utf-8")
        result = parser.parse_csv_file(path, ARTIST_ID)
        assert result["type"] == "release_summary"
        assert len(result["data"]) == 1
        assert result["source_file"] == "release_summary.csv"

    def test_sales_detail_file(self, tmp_path):
        csv = (
            "Sales date,Statement date,ISRC,Shop,Country,Transaction type,"
            "Release title,Quantity,Revenue EUR\n"
            "2024-01,2024-02,FR1234567890,Spotify,FR,stream,Album,100,5.0\n"
        )
        path = tmp_path / "sales_detail.csv"
        path.write_text(csv, encoding="utf-8")
        result = parser.parse_csv_file(path, ARTIST_ID)
        assert result["type"] == "sales_detail"
        assert len(result["data"]) == 1

    def test_unknown_columns_returns_none_type(self, tmp_path):
        csv = "foo,bar\n1,2\n"
        path = tmp_path / "garbage.csv"
        path.write_text(csv, encoding="utf-8")
        result = parser.parse_csv_file(path, ARTIST_ID)
        assert result["type"] is None
        assert result["data"] == []

    def test_nonexistent_file_returns_none_type(self):
        result = parser.parse_csv_file(Path("/nonexistent/file.csv"), ARTIST_ID)
        assert result["type"] is None
        assert result["data"] == []

    def test_latin1_encoding_fallback(self, tmp_path):
        csv = (
            "Statement date,Release title,Track streams,Total revenue\n"
            "2024-01,Caf\xe9 Album,1000,10.0\n"  # \xe9 = é in latin-1
        )
        path = tmp_path / "latin1_release.csv"
        path.write_bytes(csv.encode("latin-1"))
        result = parser.parse_csv_file(path, ARTIST_ID)
        assert result["type"] == "release_summary"
        assert "Caf" in result["data"][0]["release_title"]
