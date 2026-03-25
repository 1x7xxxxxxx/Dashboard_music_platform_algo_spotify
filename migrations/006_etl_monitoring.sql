-- Migration 006 — ETL run log + circuit breaker tables
-- Run: Get-Content migrations/006_etl_monitoring.sql | docker exec -i postgres_spotify_airflow psql -U postgres -d spotify_etl

-- ── ETL run log ──────────────────────────────────────────────────
-- Persists every DAG run outcome: duration, rows, errors, status.
-- Viewable in dashboard → "Historique ETL".

CREATE TABLE IF NOT EXISTS etl_run_log (
    id              SERIAL PRIMARY KEY,
    dag_id          VARCHAR(100) NOT NULL,
    artist_id       INTEGER,
    platform        VARCHAR(50),
    run_id          VARCHAR(200),
    started_at      TIMESTAMP NOT NULL,
    ended_at        TIMESTAMP,
    duration_ms     INTEGER,
    rows_inserted   INTEGER DEFAULT 0,
    rows_failed     INTEGER DEFAULT 0,
    status          VARCHAR(20) NOT NULL DEFAULT 'running',
    error_type      VARCHAR(100),
    error_message   TEXT,
    extra_context   JSONB,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON COLUMN etl_run_log.status IS 'running | success | failed | skipped | partial';

CREATE INDEX IF NOT EXISTS idx_etl_run_log_dag
    ON etl_run_log(dag_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_etl_run_log_status
    ON etl_run_log(status, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_etl_run_log_platform
    ON etl_run_log(platform, started_at DESC);

-- ── Circuit breaker ───────────────────────────────────────────────
-- Tracks per-platform failure state to avoid burning retries on
-- known-broken credentials or APIs.
-- States: closed (normal) | open (stop retrying) | half_open (test allowed)

CREATE TABLE IF NOT EXISTS etl_circuit_breaker (
    id              SERIAL PRIMARY KEY,
    platform        VARCHAR(50)  NOT NULL,
    artist_id       INTEGER      NOT NULL DEFAULT 0,
    state           VARCHAR(20)  NOT NULL DEFAULT 'closed',
    failure_count   INTEGER      DEFAULT 0,
    last_failure_at TIMESTAMP,
    opened_at       TIMESTAMP,
    reset_at        TIMESTAMP,
    last_error      TEXT,
    updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_circuit_platform_artist UNIQUE(platform, artist_id)
);

COMMENT ON COLUMN etl_circuit_breaker.state IS 'closed | open | half_open';
COMMENT ON COLUMN etl_circuit_breaker.reset_at IS 'When to attempt half_open again';
