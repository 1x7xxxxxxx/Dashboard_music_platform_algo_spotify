"""PostgreSQL schema for the global algorithmic lifecycle benchmark.

Type: Sub
Depends on: postgres_handler.PostgresHandler
Persists in: PostgreSQL spotify_etl

`algo_lifecycle_benchmark` holds GLOBAL (non-tenant) cohort curves describing how
the standardization ratio (a song's algo streams / its weight-category average)
evolves with song age, per algorithm (DW / RR / Radio). It is read-only at
runtime — populated once via migration from an offline export
(machine_learning/export_lifecycle_benchmark.py). Because it is never written via
upsert_many/insert_many, it is intentionally NOT in _ALLOWED_TABLES.
"""

SCHEMA = {
    "algo_lifecycle_benchmark": """
        CREATE TABLE IF NOT EXISTS algo_lifecycle_benchmark (
            id                   SERIAL PRIMARY KEY,
            algorithm            TEXT NOT NULL,          -- 'DW' | 'RR' | 'RADIO'
            weight_category_type TEXT NOT NULL,          -- 'follower_decile' | 'popularity_bucket'
            age_week_bin         TEXT NOT NULL,          -- '0-5', '5-10', ...
            age_week_bin_order   SMALLINT NOT NULL,      -- x-axis ordering
            ratio_min            DOUBLE PRECISION,
            ratio_q1             DOUBLE PRECISION,
            ratio_median         DOUBLE PRECISION,
            ratio_q3             DOUBLE PRECISION,
            ratio_max            DOUBLE PRECISION,
            total_stream_median  DOUBLE PRECISION,       -- bridge for live total-vs-total overlay
            sample_count         INTEGER NOT NULL,
            dataset_version      TEXT NOT NULL DEFAULT 'v1',
            exported_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (algorithm, age_week_bin, dataset_version)
        );

        CREATE INDEX IF NOT EXISTS idx_algo_lifecycle_lookup
        ON algo_lifecycle_benchmark (dataset_version, algorithm, age_week_bin_order);
    """,
}


def create_benchmark_tables(db) -> None:
    """Create the lifecycle benchmark table(s)."""
    for ddl in SCHEMA.values():
        db.execute_query(ddl)
