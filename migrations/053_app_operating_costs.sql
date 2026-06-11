-- 053_app_operating_costs.sql
-- Admin-global operating-cost ledger (platform costs, NOT per-tenant): domain,
-- VPS, Claude Code, Stripe fees, etc. Paired with the Supervision MRR view to
-- compute net margin. Recurring model: one row declares a charge (monthly / yearly
-- / one_off) from start_month, repeated automatically until end_month (NULL =
-- ongoing) — the monthly series is expanded in Python (app_costs.expand_monthly_costs),
-- never stored per-month. Idempotent.

CREATE TABLE IF NOT EXISTS app_operating_costs (
    id             SERIAL PRIMARY KEY,
    category       TEXT    NOT NULL,                 -- 'domain','vps','claude_code','stripe','other'
    label          TEXT,                             -- free-text name (e.g. "Hetzner CX22")
    amount_eur     NUMERIC(12, 2) NOT NULL CHECK (amount_eur >= 0),
    billing_period TEXT    NOT NULL DEFAULT 'monthly'
                   CHECK (billing_period IN ('monthly', 'yearly', 'one_off')),
    start_month    DATE    NOT NULL,                 -- first month it applies (normalised to day 1)
    end_month      DATE,                             -- last month inclusive; NULL = ongoing
    active         BOOLEAN NOT NULL DEFAULT TRUE,    -- soft-stop without deleting history
    note           TEXT,
    created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_app_operating_costs_active_start
    ON app_operating_costs (active, start_month);
