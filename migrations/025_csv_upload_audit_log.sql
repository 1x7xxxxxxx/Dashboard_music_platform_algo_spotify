-- Migration 025: CSV upload audit log
-- Tracks every file-level import: filename, platform, row count, status, timestamp.
-- collected_at on each data row serves as row-level trail; this table adds file-level traceability.

CREATE TABLE IF NOT EXISTS csv_upload_log (
    id            SERIAL PRIMARY KEY,
    artist_id     INTEGER     NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
    filename      TEXT        NOT NULL,
    platform      TEXT        NOT NULL,  -- platform key: s4a, apple, imusician_summary, …
    row_count     INTEGER     NOT NULL DEFAULT 0,
    status        TEXT        NOT NULL CHECK (status IN ('success', 'error')),
    error_message TEXT,
    imported_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS csv_upload_log_artist_idx ON csv_upload_log (artist_id, imported_at DESC);
