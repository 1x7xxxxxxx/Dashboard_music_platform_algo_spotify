-- 055_sacem_statement.sql
-- SACEM account statement (relevé de compte) — a ledger of royalty distributions
-- (line_type='repartition' = gross royalties), social charges (CSG/CRDS/URSSAF),
-- TVA, membership fees and bank payouts (virement). Parsed from the SACEM .xlsx export.
-- The ROI Breakeven sums the 'repartition' lines per month as gross royalty revenue
-- (alongside iMusician/DistroKid); the SACEM view shows gross/charges/net. Idempotent.

CREATE TABLE IF NOT EXISTS sacem_statement (
    id            SERIAL PRIMARY KEY,
    artist_id     INTEGER NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
    line_date     DATE    NOT NULL,
    libelle       TEXT    NOT NULL,
    mouvement_eur NUMERIC(12, 2) NOT NULL DEFAULT 0,   -- + income, − deduction/payout
    solde_eur     NUMERIC(12, 2) NOT NULL DEFAULT 0,   -- running balance
    line_type     TEXT    NOT NULL DEFAULT 'other',    -- repartition|charge|tva|admission|payout|balance|other
    source        TEXT    NOT NULL DEFAULT 'sacem_xlsx',
    created_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE (artist_id, line_date, libelle, mouvement_eur, solde_eur)
);

CREATE INDEX IF NOT EXISTS idx_sacem_statement_artist_date
    ON sacem_statement (artist_id, line_date);
CREATE INDEX IF NOT EXISTS idx_sacem_statement_type
    ON sacem_statement (artist_id, line_type);
