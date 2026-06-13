"""Schéma PostgreSQL pour DistroKid — revenus mensuels (saisie manuelle, phase 1).

Type: Sub
Uses: PostgresHandler
Persists in: distrokid_monthly_revenue
Mirrors imusician_schema.py; the TSV import tables (sales detail) are phase 2 —
see .claude/dev-docs/distrokid-export-format.md.
"""

DISTROKID_SCHEMA = {
    'distrokid_monthly_revenue': """
        CREATE TABLE IF NOT EXISTS distrokid_monthly_revenue (
            id SERIAL PRIMARY KEY,
            artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
            year INTEGER NOT NULL,
            month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
            revenue_eur NUMERIC(10, 2) NOT NULL DEFAULT 0,
            fx_rate NUMERIC(8, 5),
            notes TEXT,
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_distrokid_artist_month UNIQUE(artist_id, year, month)
        );

        CREATE INDEX IF NOT EXISTS idx_distrokid_revenue_artist
        ON distrokid_monthly_revenue(artist_id);

        CREATE INDEX IF NOT EXISTS idx_distrokid_revenue_period
        ON distrokid_monthly_revenue(year DESC, month DESC);
    """
}


def create_distrokid_tables():
    """Crée les tables DistroKid dans PostgreSQL."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from src.database.postgres_handler import PostgresHandler
    db = PostgresHandler.from_env_or_config()
    try:
        for table_name, sql in DISTROKID_SCHEMA.items():
            db.execute_query(sql)
            print(f"✅ {table_name} créée/vérifiée")
    finally:
        db.close()


if __name__ == "__main__":
    create_distrokid_tables()
