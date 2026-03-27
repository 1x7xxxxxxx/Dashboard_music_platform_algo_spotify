"""iMusician CSV parser — two export formats.

Type: Sub
Depends on: pandas
Persists in: imusician_release_summary, imusician_sales_detail (via caller)

Two CSV formats exported from iMusician:
  - release_summary : "Résumé par sortie" — monthly totals per release
  - sales_detail    : "Rapport de vente"  — per-ISRC/shop/country line items
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class IMusicianCSVParser:
    """Parse iMusician CSV exports (release summary and sales detail)."""

    # ─────────────────────────────────────────────
    # Type detection
    # ─────────────────────────────────────────────

    @staticmethod
    def detect_csv_type(df: pd.DataFrame) -> Optional[str]:
        """Return 'release_summary', 'sales_detail', or None.

        release_summary: has 'Release title' + 'Track streams' + 'Total revenue', no 'Sales date'
        sales_detail:    has 'Sales date' + 'ISRC' + 'Shop'
        """
        cols = {c.strip().lower() for c in df.columns}

        has_sales_date = 'sales date' in cols
        has_isrc = 'isrc' in cols
        has_shop = 'shop' in cols
        has_track_streams = 'track streams' in cols
        has_total_revenue = 'total revenue' in cols
        has_release_title = 'release title' in cols

        if has_sales_date and has_isrc and has_shop:
            return 'sales_detail'

        if has_release_title and has_track_streams and has_total_revenue and not has_sales_date:
            return 'release_summary'

        return None

    # ─────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────

    @staticmethod
    def _parse_yyyymm(val) -> Tuple[int, int]:
        """Parse 'YYYY-MM' → (year, month). Raises ValueError on invalid input."""
        if pd.isna(val):
            raise ValueError(f"Empty date value: {val!r}")
        s = str(val).strip()
        parts = s.split('-')
        if len(parts) < 2:
            raise ValueError(f"Cannot parse date: {s!r}")
        return int(parts[0]), int(parts[1])

    @staticmethod
    def _clean_numeric(val, dtype=float):
        """Convert value to float (or int), returning 0 on null/error."""
        if pd.isna(val):
            return dtype(0)
        try:
            return dtype(str(val).replace(',', '.').strip())
        except (ValueError, TypeError):
            return dtype(0)

    @staticmethod
    def _col(df: pd.DataFrame, name: str) -> Optional[str]:
        """Case-insensitive column lookup. Returns actual column name or None."""
        for c in df.columns:
            if c.strip().lower() == name.lower():
                return c
        return None

    # ─────────────────────────────────────────────
    # Parsers
    # ─────────────────────────────────────────────

    def parse_release_summary(self, df: pd.DataFrame, artist_id: int) -> List[Dict]:
        """Parse a 'Résumé par sortie' CSV into a list of dicts for imusician_release_summary."""
        df = df.dropna(how='all')
        rows = []

        for idx, row in df.iterrows():
            try:
                stmt_col = self._col(df, 'Statement date')
                year, month = self._parse_yyyymm(row[stmt_col])

                rows.append({
                    'artist_id':                  artist_id,
                    'year':                       year,
                    'month':                      month,
                    'release_title':              str(row[self._col(df, 'Release title')] or '').strip() or None,
                    'barcode':                    str(row[self._col(df, 'Barcode')] or '').strip() or None if self._col(df, 'Barcode') else None,
                    'track_downloads':            self._clean_numeric(row.get(self._col(df, 'Track downloads') or ''), int),
                    'track_streams':              self._clean_numeric(row.get(self._col(df, 'Track streams') or ''), int),
                    'release_downloads':          self._clean_numeric(row.get(self._col(df, 'Release downloads') or ''), int),
                    'track_downloads_revenue':    self._clean_numeric(row.get(self._col(df, 'Track downloads revenue') or '')),
                    'track_streams_revenue':      self._clean_numeric(row.get(self._col(df, 'Track streams revenue') or '')),
                    'release_downloads_revenue':  self._clean_numeric(row.get(self._col(df, 'Release downloads revenue') or '')),
                    'total_revenue':              self._clean_numeric(row.get(self._col(df, 'Total revenue') or '')),
                    'collected_at':               datetime.now(),
                })
            except Exception as e:
                logger.warning(f"Row {idx} skipped: {e}")
                continue

        logger.info(f"release_summary: {len(rows)} rows parsed")
        return rows

    def parse_sales_detail(self, df: pd.DataFrame, artist_id: int) -> List[Dict]:
        """Parse a 'Rapport de vente' CSV into a list of dicts for imusician_sales_detail."""
        df = df.dropna(how='all')
        rows = []

        for idx, row in df.iterrows():
            try:
                sales_year, sales_month       = self._parse_yyyymm(row[self._col(df, 'Sales date')])
                statement_year, statement_month = self._parse_yyyymm(row[self._col(df, 'Statement date')])

                rows.append({
                    'artist_id':       artist_id,
                    'sales_year':      sales_year,
                    'sales_month':     sales_month,
                    'statement_year':  statement_year,
                    'statement_month': statement_month,
                    'release_title':   str(row.get(self._col(df, 'Release title') or '', '') or '').strip() or None,
                    'barcode':         str(row.get(self._col(df, 'Barcode') or '', '') or '').strip() or None,
                    'label':           str(row.get(self._col(df, 'Label') or '', '') or '').strip() or None,
                    'isrc':            str(row[self._col(df, 'ISRC')] or '').strip() or None,
                    'track_title':     str(row.get(self._col(df, 'Track title') or '', '') or '').strip() or None,
                    'track_version':   str(row.get(self._col(df, 'Track version') or '', '') or '').strip() or None,
                    'shop':            str(row[self._col(df, 'Shop')] or '').strip() or None,
                    'transaction_type': str(row.get(self._col(df, 'Transaction type') or '', '') or '').strip() or None,
                    'country':         str(row.get(self._col(df, 'Country') or '', '') or '').strip() or None,
                    'quantity':        self._clean_numeric(row.get(self._col(df, 'Quantity') or ''), int),
                    'revenue_eur':     self._clean_numeric(row.get(self._col(df, 'Revenue EUR') or '')),
                    'collected_at':    datetime.now(),
                })
            except Exception as e:
                logger.warning(f"Row {idx} skipped: {e}")
                continue

        # Deduplicate: iMusician sometimes emits multiple sub-lines per
        # (isrc, shop, country, transaction_type, month) key. Aggregate
        # quantity and revenue_eur so a single upsert batch has no duplicates.
        CONFLICT_KEYS = [
            'artist_id', 'isrc', 'sales_year', 'sales_month',
            'statement_year', 'statement_month', 'shop', 'country', 'transaction_type',
        ]
        aggregated: dict = {}
        for r in rows:
            key = tuple(r[k] for k in CONFLICT_KEYS)
            if key in aggregated:
                aggregated[key]['quantity']    += r['quantity']
                aggregated[key]['revenue_eur'] += r['revenue_eur']
            else:
                aggregated[key] = dict(r)

        deduped = list(aggregated.values())
        if len(deduped) < len(rows):
            logger.info(f"sales_detail: {len(rows)} raw rows → {len(deduped)} after dedup")
        else:
            logger.info(f"sales_detail: {len(deduped)} rows parsed")
        return deduped

    # ─────────────────────────────────────────────
    # Entry point
    # ─────────────────────────────────────────────

    def parse_csv_file(self, file_path: Path, artist_id: int) -> Dict:
        """Parse an iMusician CSV file with encoding fallback.

        Returns {'type': str|None, 'data': list, 'source_file': str}.
        """
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
        df = None
        for enc in encodings:
            try:
                df = pd.read_csv(file_path, encoding=enc)
                logger.info(f"Encoding OK: {enc} — {file_path.name}")
                break
            except (UnicodeDecodeError, Exception):
                continue

        if df is None:
            logger.error(f"Cannot read {file_path.name} with any supported encoding")
            return {'type': None, 'data': [], 'source_file': str(file_path.name)}

        csv_type = self.detect_csv_type(df)
        if csv_type is None:
            logger.error(f"Unknown CSV type for {file_path.name}. Columns: {list(df.columns)}")
            return {'type': None, 'data': [], 'source_file': str(file_path.name)}

        if csv_type == 'release_summary':
            data = self.parse_release_summary(df, artist_id)
        else:
            data = self.parse_sales_detail(df, artist_id)

        return {'type': csv_type, 'data': data, 'source_file': str(file_path.name)}
