# DistroKid export format — reference for the phase-2 parser (B2)

Researched 2026-06-10 (web). Phase 1 (manual entry, migration 050) AND phase 2
(parser `distrokid_parser.py`, `distrokid_sales_detail` migration 051, USD→EUR
rollup `distrokid_rollup.py`, Upload CSV + `distrokid_csv_watcher` DAG) are both
shipped — this doc remains the format reference. Test fixture:
`tests/fixtures/distrokid_bank_sample.csv` (22 rows from the BetterKid sample).

## The "Bank details" export

- Source: DistroKid → Bank → "SEE EXCRUCIATING DETAIL" → Download
  (`distrokid.com/bank/details/`). **FR UI** (account-language-dependent):
  **Banque → "Voir dans le moindre détail" → Download**.
- Format: **tab-delimited** `.tsv` (some sources report a `.zip` containing `.csv` —
  detect the delimiter at parse time, like `IMusicianCSVParser`'s encoding fallback).
- Line endings: a real 2026 export (`DistroKid_*.tsv`, artist "Benken") shipped with
  **CR-only (`\r`) terminators** (classic-Mac style, 0 `\n`). pandas' C parser handles
  these transparently — verified end-to-end (331 rows parsed). The `_sniff_sep` split on
  `\n` degrades to "whole file = first line" but still counts tabs > commas → picks `\t`.
- Encoding: usually **latin-1**, but the same 2026 export decoded clean as **UTF-8** too —
  the utf-8 → utf-8-sig → latin-1 → cp1252 fallback covers both.
  Fallback chain utf-8 → utf-8-sig → latin-1 → cp1252 already exists in
  `src/transformers/imusician_csv_parser.py::_read_csv` — reuse it.
- Granularity: **1 row per store × track × country × sale-month**. No sub-monthly data.
- Currency: **USD** (the live table is EUR — the parser will need `revenue_usd` +
  `fx_rate` → `revenue_eur`, decided 2026-06-10).
- Exports > 50 000 rows require pre-filtering (date range/store/artist/release) and are
  generated asynchronously. ~150k rows ≈ 14 MB.

## Columns (post-July-2025 schema, 15 columns)

| Column | Type / example |
|---|---|
| `Date Inserted` | date — when DistroKid ingested the row |
| `Reporting Date` | date — when DistroKid received the store payment (use for accounting) |
| `Sale Month` | `YYYY-MM` — when the stream/sale happened (lags 2–6 months by store) |
| `Store` | `Spotify`, `Apple Music`, `Amazon`, … |
| `Artist` | string |
| `Title` | track or album title |
| `ISRC` | string |
| `UPC` | string |
| `Quantity` | int — streams or download units |
| `Team Percentage` | numeric — split % for this member |
| `Source Type` | `Song` / `Album` (verified on the BetterKid sample — renamed `Song/Album` column) |
| `Country of Sale` | ISO-2 country code |
| `Songwriter Royalties Withheld (USD)` | decimal |
| `Earnings (USD)` | decimal |
| `Recoup (USD)` | decimal — label-deal recoupment |

## Gotchas

- **July 2025 schema change**: pre-2025 files have fewer columns (`Song/Album` instead
  of `Source Type`, no `Date Inserted`/`Team Percentage`/`Recoup`). Support both or
  gate on header detection.
- **Column *name* and column *count* are independent axes**: a real 2026 export had the
  **full 15-column layout** (incl. `Date Inserted`, `Team Percentage`, `Recoup (USD)`)
  yet still labelled the type column **`Song/Album`**, not `Source Type`. So don't infer
  the schema age from the type-column name. The parser already covers this — it reads
  `Source Type` then falls back to `Song/Album` (`distrokid_parser.py:137`).
- `Sale Month` is the natural key for the monthly rollup (≙ iMusician `sales_year/month`);
  `Reporting Date` ≙ iMusician `statement_year/month`.
- Candidate UNIQUE for a future `distrokid_sales_detail`:
  `(artist_id, isrc, sale_month, reporting_date, store, country, source_type)` —
  aggregate duplicates pre-upsert like `IMusicianCSVParser.parse_sales_detail`.

## References

- Help: support.distrokid.com — "Saving Your Earnings Information as a Spreadsheet File",
  "Using the DistroKid Bank to See Your Earnings"
- `github.com/DJSethDuncan/betterkid` — current-schema reference; its `sample-data.csv`
  is a ready-made test fixture for the parser
- `github.com/mkgs/distrokid-tsv` — minimal pre-2025 parser (`delimiter='\t'`,
  `encoding='latin-1'`)
- Infinite Catalog KB — documents the legacy vs post-July-2025 importer split
