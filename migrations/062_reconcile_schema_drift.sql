-- 062_reconcile_schema_drift.sql
-- Reconcile the version-controlled schema with prod for the USED-but-undeclared
-- items found by `make schema-check` (2026-06-13, see .claude/dev-docs/
-- schema-drift-2026-06-13.md). These columns/tables exist in prod and are read by
-- code, but were never declared in init_db.sql/migrations → a fresh install (CI)
-- lacked them and 500'd. Idempotent: safe to re-apply (prod already has them).

-- etl_daily_metrics — read by views/airflow_kpi.py, created on prod outside any
-- migration. Mirrors prod (PK id + UNIQUE(dag_id, run_date)). ETL monitoring tables
-- live in migrations (cf. 006_etl_monitoring.sql), not init_db.sql.
CREATE TABLE IF NOT EXISTS etl_daily_metrics (
    id                      SERIAL PRIMARY KEY,
    dag_id                  TEXT NOT NULL,
    run_date                DATE DEFAULT CURRENT_DATE,
    total_rows              INTEGER DEFAULT 0,
    invalid_rows            INTEGER DEFAULT 0,
    anomalies_confirmed     INTEGER DEFAULT 0,
    api_availability_status BOOLEAN DEFAULT TRUE,
    alert_delay_seconds     INTEGER DEFAULT 0,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT etl_daily_metrics_dag_id_run_date_key UNIQUE (dag_id, run_date)
);

-- apple_songs_performance — extra per-song Apple metrics read by the Apple Music view.
ALTER TABLE apple_songs_performance ADD COLUMN IF NOT EXISTS shazam_count INTEGER DEFAULT 0;
ALTER TABLE apple_songs_performance ADD COLUMN IF NOT EXISTS radio_spins  INTEGER DEFAULT 0;
ALTER TABLE apple_songs_performance ADD COLUMN IF NOT EXISTS purchases    INTEGER DEFAULT 0;

-- meta_adsets — age-range targeting label read by the Meta breakdown views.
ALTER TABLE meta_adsets ADD COLUMN IF NOT EXISTS age_range TEXT;
