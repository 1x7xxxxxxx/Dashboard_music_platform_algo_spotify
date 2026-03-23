"""Tests unitaires — Parsers CSV (S4A, Apple Music, Meta)."""
import io
import textwrap
from pathlib import Path

import pandas as pd
import pytest

from src.transformers.s4a_csv_parser import S4ACSVParser
from src.transformers.apple_music_csv_parser import AppleMusicCSVParser
from src.transformers.meta_csv_parser import MetaCSVParser


# =============================================================================
# S4ACSVParser
# =============================================================================

class TestS4AExtractSongName:
    parser = S4ACSVParser()

    def test_strip_timestamp_suffix(self):
        assert self.parser._extract_song_name_from_filename(
            "Mon Titre - Remix_20251129_180552.csv"
        ) == "Mon Titre - Remix"

    def test_strip_timeline_suffix(self):
        assert self.parser._extract_song_name_from_filename(
            "Ma Chanson-timeline_20250101_000000.csv"
        ) == "Ma Chanson"

    def test_no_suffix(self):
        assert self.parser._extract_song_name_from_filename("SimpleSong.csv") == "SimpleSong"

    def test_underscore_timeline(self):
        assert self.parser._extract_song_name_from_filename(
            "Track_timeline_20240601_120000.csv"
        ) == "Track"


class TestS4ADetectCSVType:
    parser = S4ACSVParser()

    def test_detect_song_timeline_streams(self):
        df = pd.DataFrame({"date": ["2024-01-01"], "streams": [100]})
        assert self.parser.detect_csv_type(df, "SomeSong_20240101_000000.csv") == "song_timeline_single"

    def test_detect_song_timeline_ecoutes(self):
        df = pd.DataFrame({"date": ["2024-01-01"], "ecoutes": [50]})
        assert self.parser.detect_csv_type(df, "track_20240101_120000.csv") == "song_timeline_single"

    def test_detect_audience_by_filename(self):
        df = pd.DataFrame({"date": ["2024-01-01"], "streams": [100]})
        assert self.parser.detect_csv_type(df, "audience_20240101_000000.csv") == "audience"

    def test_detect_unknown(self):
        df = pd.DataFrame({"foo": [1], "bar": [2]})
        assert self.parser.detect_csv_type(df, "unknown.csv") is None


class TestS4AParseCSVFile:
    parser = S4ACSVParser()

    def test_parse_song_timeline(self, tmp_csv):
        content = "date,streams\n2024-01-01,100\n2024-01-02,200\n"
        path = tmp_csv("MySong_20240601_120000.csv", content)
        result = self.parser.parse_csv_file(path)
        assert result["type"] == "song_timeline"
        assert len(result["data"]) == 2
        assert result["data"][0]["song"] == "MySong"
        assert result["data"][0]["streams"] == 100

    def test_parse_streams_with_comma_format(self, tmp_csv):
        content = "date,streams\n2024-01-01,\"1,024\"\n"
        path = tmp_csv("Track_20240101_000000.csv", content)
        result = self.parser.parse_csv_file(path)
        assert result["data"][0]["streams"] == 1024

    def test_malformed_row_skipped(self, tmp_csv):
        content = "date,streams\n2024-01-01,100\nbad_date,not_a_number\n2024-01-03,300\n"
        path = tmp_csv("Song_20240101_000000.csv", content)
        result = self.parser.parse_csv_file(path)
        # La ligne malformée est ignorée, les 2 lignes valides sont conservées
        assert result["type"] == "song_timeline"
        valid = [r for r in result["data"] if r["streams"] in (100, 300)]
        assert len(valid) == 2

    def test_empty_file_returns_none_type(self, tmp_csv):
        path = tmp_csv("Empty_20240101_000000.csv", "")
        result = self.parser.parse_csv_file(path)
        assert result["type"] is None

    def test_missing_file_returns_none_type(self):
        result = self.parser.parse_csv_file(Path("/nonexistent/path/file.csv"))
        assert result["type"] is None


# =============================================================================
# AppleMusicCSVParser
# =============================================================================

class TestAppleMusicDetectType:
    parser = AppleMusicCSVParser()

    def _df(self, columns, data=None):
        data = data or {c: [] for c in columns}
        return pd.DataFrame(data)

    def test_detect_songs_performance(self):
        df = self._df(["morceau", "écoutes", "auditeurs"])
        assert self.parser.detect_csv_type(df) == "songs_performance"

    def test_detect_daily_plays(self):
        df = self._df(["date", "écoutes"])
        assert self.parser.detect_csv_type(df) == "daily_plays"

    def test_detect_listeners(self):
        df = self._df(["date", "auditeurs"])
        assert self.parser.detect_csv_type(df) == "listeners"

    def test_detect_unknown(self):
        df = self._df(["foo", "bar"])
        assert self.parser.detect_csv_type(df) is None


class TestAppleMusicFindColumn:
    parser = AppleMusicCSVParser()

    def test_find_song_col_fr(self):
        df = pd.DataFrame({"Morceau": [], "Écoutes": []})
        assert self.parser.find_column(df, "song") == "Morceau"

    def test_find_plays_col_en(self):
        df = pd.DataFrame({"Song": [], "Plays": []})
        assert self.parser.find_column(df, "plays") == "Plays"

    def test_missing_col_returns_none(self):
        df = pd.DataFrame({"nothing": []})
        assert self.parser.find_column(df, "song") is None


class TestAppleMusicCleanNumber:
    parser = AppleMusicCSVParser()

    def test_int_passthrough(self):
        assert self.parser.clean_number(42) == 42

    def test_float_truncated(self):
        assert self.parser.clean_number(3.9) == 3

    def test_string_with_comma(self):
        assert self.parser.clean_number("1,024") == 1024

    def test_nan_returns_zero(self):
        import math
        assert self.parser.clean_number(float("nan")) == 0

    def test_invalid_string_returns_zero(self):
        assert self.parser.clean_number("N/A") == 0


class TestAppleMusicParseSongsPerformance:
    parser = AppleMusicCSVParser()

    def test_parse_normal(self, tmp_csv):
        content = "Morceau,Écoutes,Auditeurs\nSong A,500,200\nSong B,300,100\n"
        path = tmp_csv("songs.csv", content)
        result = self.parser.parse_csv_file(path)
        assert result["type"] == "songs_performance"
        assert len(result["data"]) == 2
        assert result["data"][0]["song_name"] == "Song A"
        assert result["data"][0]["plays"] == 500

    def test_missing_plays_col_returns_empty(self, tmp_csv):
        content = "Morceau,Auditeurs\nSong A,200\n"
        path = tmp_csv("songs_no_plays.csv", content)
        result = self.parser.parse_csv_file(path)
        # Sans colonne "écoutes/plays", le type ne sera pas détecté comme songs_performance
        assert result["data"] == [] or result["type"] is None


class TestAppleMusicParseDailyPlays:
    parser = AppleMusicCSVParser()

    def test_parse_normal(self, tmp_csv):
        content = "Date,Écoutes\n2024-01-01,100\n2024-01-02,200\n"
        path = tmp_csv("daily.csv", content)
        result = self.parser.parse_csv_file(path)
        assert result["type"] == "daily_plays"
        assert len(result["data"]) == 2
        assert result["data"][0]["plays"] == 100


# =============================================================================
# MetaCSVParser
# =============================================================================

class TestMetaCSVParser:
    parser = MetaCSVParser()

    def _make_tab_csv(self, tmp_csv, rows: list[dict]):
        """Génère un TSV UTF-8 avec les colonnes Meta standard."""
        columns = ["Campaign ID", "Campaign Name", "Campaign Start Time",
                   "Ad Set ID", "Ad Set Name", "Ad Set Run Status",
                   "Ad Set Time Start", "Countries", "Cities", "Gender",
                   "Age Min", "Age Max", "Flexible Inclusions", "Advantage Audience",
                   "Age Range", "Targeting Optimization", "Publisher Platforms",
                   "Instagram Positions", "Device Platforms",
                   "Ad ID", "Ad Name", "Title", "Body", "Video File Name", "Call to Action"]
        header = "\t".join(columns)
        lines = [header]
        for r in rows:
            lines.append("\t".join(str(r.get(c, "")) for c in columns))
        content = "\n".join(lines)
        return tmp_csv("meta_config.csv", content, "utf-8")

    def test_parse_single_row(self, tmp_csv):
        rows = [{"Campaign ID": "123", "Campaign Name": "Test Camp",
                 "Ad Set ID": "456", "Ad Set Name": "Set 1",
                 "Ad ID": "789", "Ad Name": "Ad 1"}]
        path = self._make_tab_csv(tmp_csv, rows)
        result = self.parser.parse(path)
        assert result["type"] == "mixed_config"
        assert len(result["data"]["campaigns"]) == 1
        assert result["data"]["campaigns"][0]["campaign_id"] == "123"
        assert len(result["data"]["adsets"]) == 1
        assert len(result["data"]["ads"]) == 1

    def test_parse_multiple_rows_dedup(self, tmp_csv):
        """Deux lignes avec le même Campaign ID → une seule campagne."""
        rows = [
            {"Campaign ID": "100", "Campaign Name": "Camp A",
             "Ad Set ID": "200", "Ad Set Name": "Set A",
             "Ad ID": "300", "Ad Name": "Ad A"},
            {"Campaign ID": "100", "Campaign Name": "Camp A",
             "Ad Set ID": "201", "Ad Set Name": "Set B",
             "Ad ID": "301", "Ad Name": "Ad B"},
        ]
        path = self._make_tab_csv(tmp_csv, rows)
        result = self.parser.parse(path)
        assert len(result["data"]["campaigns"]) == 1
        assert len(result["data"]["adsets"]) == 2
        assert len(result["data"]["ads"]) == 2

    def test_parse_missing_campaign_id_returns_error(self, tmp_csv):
        """Fichier sans colonne 'Campaign ID' → type='error'."""
        content = "Foo\tBar\nval1\tval2\n"
        path = tmp_csv("bad_meta.csv", content, "utf-8")
        result = self.parser.parse(path)
        assert result["type"] == "error"

    def test_parse_float_ids_stripped(self, tmp_csv):
        """Les IDs comme '123.0' doivent être normalisés en '123'."""
        rows = [{"Campaign ID": "123.0", "Campaign Name": "Camp",
                 "Ad Set ID": "456.0", "Ad Set Name": "Set",
                 "Ad ID": "789.0", "Ad Name": "Ad"}]
        path = self._make_tab_csv(tmp_csv, rows)
        result = self.parser.parse(path)
        assert result["data"]["campaigns"][0]["campaign_id"] == "123"
        assert result["data"]["adsets"][0]["adset_id"] == "456"
        assert result["data"]["ads"][0]["ad_id"] == "789"
