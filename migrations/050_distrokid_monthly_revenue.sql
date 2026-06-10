-- Migration 050 — DistroKid monthly revenue (B2 phase 1: manual entry)
-- Run: make migrate   (or, from PowerShell, see CLAUDE.md § Running Migrations)
--
-- Mirrors imusician_monthly_revenue. Phase 1 is manual entry only (EUR, entered
-- by the artist from their DistroKid bank statement); the TSV "bank details"
-- import (USD, store×track×country×month granularity) is phase 2 — format
-- documented in .claude/dev-docs/distrokid-export-format.md.

CREATE TABLE IF NOT EXISTS distrokid_monthly_revenue (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    revenue_eur NUMERIC(10, 2) NOT NULL DEFAULT 0,
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

COMMENT ON TABLE distrokid_monthly_revenue IS
    'DistroKid monthly revenue per artist (EUR). source=manual (form) | import (future TSV parser).';
