"""Schéma PostgreSQL pour l'import DistroKid — lignes de vente brutes (USD).

Type: Sub
Uses: PostgresHandler
Persists in: distrokid_sales_detail
Mirrors imusician_csv_schema.py; rollup mensuel EUR → distrokid_monthly_revenue
(src/utils/distrokid_rollup.py). Format: .claude/dev-docs/distrokid-export-format.md.
"""

DISTROKID_CSV_SCHEMA = {
    'distrokid_sales_detail': """
        CREATE TABLE IF NOT EXISTS distrokid_sales_detail (
            id SERIAL PRIMARY KEY,
            artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
            sale_year INTEGER NOT NULL,
            sale_month INTEGER NOT NULL CHECK (sale_month BETWEEN 1 AND 12),
            reporting_date DATE NOT NULL,
            store TEXT NOT NULL DEFAULT '',
            artist_name TEXT,
            title TEXT NOT NULL DEFAULT '',
            isrc TEXT NOT NULL DEFAULT '',
            upc TEXT,
            quantity INTEGER NOT NULL DEFAULT 0,
            team_percentage NUMERIC(6, 2),
            source_type TEXT NOT NULL DEFAULT '',
            country TEXT NOT NULL DEFAULT '',
            songwriter_royalties_usd NUMERIC(14, 10) DEFAULT 0,
            earnings_usd NUMERIC(14, 10) NOT NULL DEFAULT 0,
            recoup_usd NUMERIC(14, 10) DEFAULT 0,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_distrokid_sale UNIQUE
                (artist_id, isrc, title, sale_year, sale_month,
                 reporting_date, store, country, source_type)
        );

        CREATE INDEX IF NOT EXISTS idx_distrokid_sales_artist
        ON distrokid_sales_detail(artist_id);

        CREATE INDEX IF NOT EXISTS idx_distrokid_sales_period
        ON distrokid_sales_detail(artist_id, sale_year DESC, sale_month DESC);

        CREATE INDEX IF NOT EXISTS idx_distrokid_sales_isrc
        ON distrokid_sales_detail(isrc);
    """
}


def create_distrokid_csv_tables():
    """Crée les tables d'import DistroKid dans PostgreSQL."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from src.database.postgres_handler import PostgresHandler
    db = PostgresHandler.from_env_or_config()
    try:
        for table_name, sql in DISTROKID_CSV_SCHEMA.items():
            db.execute_query(sql)
            print(f"✅ {table_name} créée/vérifiée")
    finally:
        db.close()


if __name__ == "__main__":
    create_distrokid_csv_tables()
