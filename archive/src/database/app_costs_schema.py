"""Schéma PostgreSQL pour les coûts d'exploitation de la plateforme (admin-global).

Type: Sub
Uses: PostgresHandler
Persists in: app_operating_costs
Platform costs (domain, VPS, Claude Code, Stripe fees…) — NOT per-tenant. Paired
with the Supervision MRR view for net margin. Recurring model: one row = one charge
(monthly/yearly/one_off) from start_month until end_month (NULL = ongoing); the
per-month series is expanded in src/dashboard/utils/app_costs.py, never stored.
Canonical CREATE mirrors migrations/053_app_operating_costs.sql for fresh installs.
"""

APP_COSTS_SCHEMA = {
    'app_operating_costs': """
        CREATE TABLE IF NOT EXISTS app_operating_costs (
            id             SERIAL PRIMARY KEY,
            category       TEXT    NOT NULL,
            label          TEXT,
            amount_eur     NUMERIC(12, 2) NOT NULL CHECK (amount_eur >= 0),
            billing_period TEXT    NOT NULL DEFAULT 'monthly'
                           CHECK (billing_period IN ('monthly', 'yearly', 'one_off')),
            start_month    DATE    NOT NULL,
            end_month      DATE,
            active         BOOLEAN NOT NULL DEFAULT TRUE,
            note           TEXT,
            created_at     TIMESTAMPTZ DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS idx_app_operating_costs_active_start
        ON app_operating_costs (active, start_month);
    """
}


def create_app_costs_tables():
    """Crée la table des coûts d'exploitation dans PostgreSQL."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from src.database.postgres_handler import PostgresHandler
    db = PostgresHandler.from_env_or_config()
    try:
        for table_name, sql in APP_COSTS_SCHEMA.items():
            db.execute_query(sql)
            print(f"✅ {table_name} créée/vérifiée")
    finally:
        db.close()


if __name__ == "__main__":
    create_app_costs_tables()
