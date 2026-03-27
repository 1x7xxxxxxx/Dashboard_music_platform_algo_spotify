"""PostgreSQL schema for iMusician CSV imports.

Type: Core
Depends on: saas_artists table, PostgresHandler
Persists in: imusician_release_summary, imusician_sales_detail

Two tables matching the two downloadable CSV formats from iMusician:
  - imusician_release_summary  : "Résumé par sortie" (per-release monthly totals)
  - imusician_sales_detail     : "Rapport de vente" (per-ISRC/shop/country line items)

The existing imusician_monthly_revenue table (manual entry) is unchanged.
"""

IMUSICIAN_CSV_SCHEMA = {
    'imusician_release_summary': """
        CREATE TABLE IF NOT EXISTS imusician_release_summary (
            id                        SERIAL PRIMARY KEY,
            artist_id                 INTEGER NOT NULL DEFAULT 1
                                      REFERENCES saas_artists(id),
            year                      INTEGER NOT NULL,
            month                     INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
            release_title             TEXT,
            barcode                   VARCHAR(20),
            track_downloads           INTEGER          DEFAULT 0,
            track_streams             INTEGER          DEFAULT 0,
            release_downloads         INTEGER          DEFAULT 0,
            track_downloads_revenue   NUMERIC(12, 8)   DEFAULT 0,
            track_streams_revenue     NUMERIC(12, 8)   DEFAULT 0,
            release_downloads_revenue NUMERIC(12, 8)   DEFAULT 0,
            total_revenue             NUMERIC(12, 8)   DEFAULT 0,
            collected_at              TIMESTAMP        DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (artist_id, barcode, year, month)
        );

        CREATE INDEX IF NOT EXISTS idx_imusician_release_summary_artist
            ON imusician_release_summary (artist_id);

        CREATE INDEX IF NOT EXISTS idx_imusician_release_summary_period
            ON imusician_release_summary (artist_id, year DESC, month DESC);

        CREATE INDEX IF NOT EXISTS idx_imusician_release_summary_barcode
            ON imusician_release_summary (barcode);
    """,

    'imusician_sales_detail': """
        CREATE TABLE IF NOT EXISTS imusician_sales_detail (
            id               SERIAL PRIMARY KEY,
            artist_id        INTEGER NOT NULL DEFAULT 1
                             REFERENCES saas_artists(id),
            sales_year       INTEGER NOT NULL,
            sales_month      INTEGER NOT NULL CHECK (sales_month BETWEEN 1 AND 12),
            statement_year   INTEGER NOT NULL,
            statement_month  INTEGER NOT NULL CHECK (statement_month BETWEEN 1 AND 12),
            release_title    TEXT,
            barcode          VARCHAR(20),
            label            TEXT,
            isrc             VARCHAR(15),
            track_title      TEXT,
            track_version    TEXT,
            shop             TEXT,
            transaction_type TEXT,
            country          VARCHAR(50),
            quantity         INTEGER        DEFAULT 0,
            revenue_eur      NUMERIC(12, 8) DEFAULT 0,
            collected_at     TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (
                artist_id, isrc, sales_year, sales_month,
                statement_year, statement_month, shop, country, transaction_type
            )
        );

        CREATE INDEX IF NOT EXISTS idx_imusician_sales_detail_artist
            ON imusician_sales_detail (artist_id);

        CREATE INDEX IF NOT EXISTS idx_imusician_sales_detail_period
            ON imusician_sales_detail (artist_id, sales_year DESC, sales_month DESC);

        CREATE INDEX IF NOT EXISTS idx_imusician_sales_detail_isrc
            ON imusician_sales_detail (isrc);

        CREATE INDEX IF NOT EXISTS idx_imusician_sales_detail_shop
            ON imusician_sales_detail (shop);
    """,
}


def create_imusician_csv_tables() -> None:
    """Create iMusician CSV tables in PostgreSQL."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from src.database.postgres_handler import PostgresHandler
    from src.utils.config_loader import config_loader

    print('\n' + '=' * 70)
    print('iMusician CSV — TABLE CREATION')
    print('=' * 70 + '\n')

    config = config_loader.load()
    db = PostgresHandler(**config['database'])

    try:
        for table_name, sql in IMUSICIAN_CSV_SCHEMA.items():
            print(f'Creating {table_name}...')
            db.execute_query(sql)
            count = db.get_table_count(table_name)
            print(f'  ✅ {table_name} — {count} existing rows')
    except Exception as e:
        print(f'  ❌ Error: {e}')
        import traceback
        traceback.print_exc()
    finally:
        db.close()

    print('\n' + '=' * 70)
    print('✅ Done')
    print('=' * 70 + '\n')


if __name__ == '__main__':
    create_imusician_csv_tables()
