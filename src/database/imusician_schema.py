"""Schéma PostgreSQL pour iMusician — revenus mensuels."""

IMUSICIAN_SCHEMA = {
    'imusician_monthly_revenue': """
        CREATE TABLE IF NOT EXISTS imusician_monthly_revenue (
            id SERIAL PRIMARY KEY,
            artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
            year INTEGER NOT NULL,
            month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
            revenue_eur NUMERIC(10, 2) NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_imusician_artist_month UNIQUE(artist_id, year, month)
        );

        CREATE INDEX IF NOT EXISTS idx_imusician_revenue_artist
        ON imusician_monthly_revenue(artist_id);

        CREATE INDEX IF NOT EXISTS idx_imusician_revenue_period
        ON imusician_monthly_revenue(year DESC, month DESC);
    """
}


def create_imusician_tables():
    """Crée les tables iMusician dans PostgreSQL."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from src.database.postgres_handler import PostgresHandler
    from src.utils.config_loader import config_loader

    config = config_loader.load()
    db = PostgresHandler(**config['database'])
    try:
        for table_name, sql in IMUSICIAN_SCHEMA.items():
            db.execute_query(sql)
            print(f"✅ {table_name} créée/vérifiée")
    finally:
        db.close()


if __name__ == "__main__":
    create_imusician_tables()
