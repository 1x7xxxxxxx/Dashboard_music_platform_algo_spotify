"""DistroKid "bank details" export parser — TSV or CSV, latin-1 friendly.

Type: Sub
Depends on: pandas
Persists in: distrokid_sales_detail (via caller)

Format reference: .claude/dev-docs/distrokid-export-format.md
One row per store × track × country × sale-month, amounts in USD.
Handles both the post-July-2025 schema (15 columns, 'Source Type') and the
legacy one ('Song/Album', fewer columns). Delimiter (tab vs comma) and
encoding (utf-8 → latin-1 → cp1252) are sniffed — DistroKid ships
tab-delimited latin-1 .tsv, but .zip/.csv variants exist in the wild.
"""
import io
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Dedup/upsert key — mirrors the UNIQUE constraint on distrokid_sales_detail.
CONFLICT_KEYS = [
    'artist_id', 'isrc', 'title', 'sale_year', 'sale_month',
    'reporting_date', 'store', 'country', 'source_type',
]

_ENCODINGS = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']


class DistroKidParser:
    """Parse DistroKid bank-details exports (sales detail rows, USD)."""

    # ─────────────────────────────────────────────
    # Detection
    # ─────────────────────────────────────────────

    @staticmethod
    def detect(columns) -> bool:
        """True when the headers look like a DistroKid bank-details export."""
        cols = {str(c).strip().lower() for c in columns}
        return 'sale month' in cols and 'earnings (usd)' in cols

    # ─────────────────────────────────────────────
    # Reading (encoding + delimiter sniffing)
    # ─────────────────────────────────────────────

    @staticmethod
    def _decode(raw: bytes) -> Optional[str]:
        for enc in _ENCODINGS:
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, ValueError):
                continue
        return None

    @staticmethod
    def _sniff_sep(text: str) -> str:
        first_line = text.split('\n', 1)[0]
        return '\t' if first_line.count('\t') > first_line.count(',') else ','

    def to_dataframe(self, raw: bytes) -> Optional[pd.DataFrame]:
        """bytes → DataFrame, or None when undecodable/unreadable."""
        text = self._decode(raw)
        if text is None:
            return None
        try:
            return pd.read_csv(io.StringIO(text), sep=self._sniff_sep(text))
        except Exception as e:
            logger.error(f"DistroKid read failed: {e}")
            return None

    # ─────────────────────────────────────────────
    # Helpers (aligned with IMusicianCSVParser)
    # ─────────────────────────────────────────────

    @staticmethod
    def _parse_yyyymm(val) -> tuple:
        if pd.isna(val):
            raise ValueError(f"Empty date value: {val!r}")
        parts = str(val).strip().split('-')
        if len(parts) < 2:
            raise ValueError(f"Cannot parse date: {val!r}")
        return int(parts[0]), int(parts[1])

    @staticmethod
    def _parse_date(val, fallback: date) -> date:
        """'YYYY-MM-DD' → date; absent/invalid → fallback (legacy files)."""
        if pd.isna(val) or not str(val).strip():
            return fallback
        try:
            return date.fromisoformat(str(val).strip().split(' ')[0].split('T')[0])
        except ValueError:
            return fallback

    @staticmethod
    def _clean_numeric(val, dtype=float):
        if pd.isna(val):
            return dtype(0)
        try:
            return dtype(float(str(val).replace(',', '.').strip()))
        except (ValueError, TypeError):
            return dtype(0)

    @staticmethod
    def _col(df: pd.DataFrame, name: str) -> Optional[str]:
        for c in df.columns:
            if str(c).strip().lower() == name.lower():
                return c
        return None

    def _text(self, df, row, name: str, default: str = '') -> str:
        col = self._col(df, name)
        if col is None or pd.isna(row.get(col)):
            return default
        return str(row[col]).strip()

    # ─────────────────────────────────────────────
    # Parser
    # ─────────────────────────────────────────────

    def parse_sales(self, df: pd.DataFrame, artist_id: int) -> List[Dict]:
        """Parse a bank-details DataFrame into rows for distrokid_sales_detail."""
        df = df.dropna(how='all')
        sale_col = self._col(df, 'Sale Month')
        earn_col = self._col(df, 'Earnings (USD)')
        if sale_col is None or earn_col is None:
            raise ValueError("Missing required column(s): Sale Month, Earnings (USD)")

        rows = []
        for idx, row in df.iterrows():
            try:
                sale_year, sale_month = self._parse_yyyymm(row[sale_col])
                # Legacy files have 'Song/Album' instead of 'Source Type'
                source_type = (self._text(df, row, 'Source Type')
                               or self._text(df, row, 'Song/Album'))
                rows.append({
                    'artist_id':       artist_id,
                    'sale_year':       sale_year,
                    'sale_month':      sale_month,
                    'reporting_date':  self._parse_date(
                        row.get(self._col(df, 'Reporting Date') or ''),
                        fallback=date(sale_year, sale_month, 1)),
                    'store':           self._text(df, row, 'Store'),
                    'artist_name':     self._text(df, row, 'Artist') or None,
                    'title':           self._text(df, row, 'Title'),
                    'isrc':            self._text(df, row, 'ISRC'),
                    'upc':             self._text(df, row, 'UPC') or None,
                    'quantity':        self._clean_numeric(row.get(self._col(df, 'Quantity') or ''), int),
                    'team_percentage': self._clean_numeric(row.get(self._col(df, 'Team Percentage') or '')),
                    'source_type':     source_type,
                    'country':         self._text(df, row, 'Country of Sale'),
                    'songwriter_royalties_usd': self._clean_numeric(
                        row.get(self._col(df, 'Songwriter Royalties Withheld (USD)') or '')),
                    'earnings_usd':    self._clean_numeric(row.get(earn_col)),
                    'recoup_usd':      self._clean_numeric(row.get(self._col(df, 'Recoup (USD)') or '')),
                    'collected_at':    datetime.now(timezone.utc),
                })
            except Exception as e:
                logger.warning(f"Row {idx} skipped: {e}")
                continue

        return self._dedup(rows)

    @staticmethod
    def _dedup(rows: List[Dict]) -> List[Dict]:
        """Aggregate rows sharing the conflict key (upsert batches must be unique)."""
        aggregated: dict = {}
        for r in rows:
            key = tuple(r[k] for k in CONFLICT_KEYS)
            if key in aggregated:
                agg = aggregated[key]
                agg['quantity'] += r['quantity']
                agg['earnings_usd'] += r['earnings_usd']
                agg['songwriter_royalties_usd'] += r['songwriter_royalties_usd']
                agg['recoup_usd'] += r['recoup_usd']
            else:
                aggregated[key] = dict(r)
        deduped = list(aggregated.values())
        if len(deduped) < len(rows):
            logger.info(f"distrokid: {len(rows)} raw rows → {len(deduped)} after dedup")
        else:
            logger.info(f"distrokid: {len(deduped)} rows parsed")
        return deduped

    # ─────────────────────────────────────────────
    # Entry points
    # ─────────────────────────────────────────────

    def parse_file(self, file_path: Path, artist_id: int) -> Dict:
        """Parse a DistroKid export from disk (DAG watcher path).

        Returns {'type': 'distrokid_sales'|None, 'data': list, 'source_file': str}.
        """
        raw = Path(file_path).read_bytes()
        return self._parse_raw(raw, artist_id, Path(file_path).name)

    def parse_upload(self, file, artist_id: int) -> List[Dict]:
        """Parse a Streamlit-uploaded file object. Raises ValueError when unreadable."""
        file.seek(0)
        result = self._parse_raw(file.read(), artist_id, getattr(file, 'name', ''))
        if result['type'] is None:
            raise ValueError("Fichier DistroKid illisible ou colonnes inattendues.")
        return result['data']

    def _parse_raw(self, raw: bytes, artist_id: int, source_name: str) -> Dict:
        df = self.to_dataframe(raw)
        if df is None:
            logger.error(f"Cannot read {source_name} with any supported encoding")
            return {'type': None, 'data': [], 'source_file': source_name}
        if not self.detect(df.columns):
            logger.error(f"Not a DistroKid bank export: {source_name}. Columns: {list(df.columns)}")
            return {'type': None, 'data': [], 'source_file': source_name}
        return {
            'type': 'distrokid_sales',
            'data': self.parse_sales(df, artist_id),
            'source_file': source_name,
        }
