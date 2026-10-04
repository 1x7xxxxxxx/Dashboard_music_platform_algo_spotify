-- 146 — hypeddit_daily_stats : the trigger that computes ctr / cost_per_click / updated_at,
-- moved into the migration chain (R396).
--
-- Additive only (CREATE OR REPLACE FUNCTION, CREATE OR REPLACE TRIGGER) — idempotent,
-- safe to replay; the body is prod's own (read 2026-10-05), trailing blanks trimmed —
-- same statements, so replaying it on prod changes no behaviour.
--
-- Why: the DDL lived only in src/database/hypeddit_schema.py, run under __main__. A base
-- rebuilt from migrations/ alone had no trigger, so ctr stayed NULL in the CSV export.
-- Found by schema-check comparing triggers (R368). The 10 local-only indexes of that file
-- are NOT added: prod has none of them, and migration 099 dropped redundant indexes on
-- purpose.

CREATE OR REPLACE FUNCTION calculate_hypeddit_metrics()
RETURNS TRIGGER AS $$
BEGIN
    -- Calcul du CTR
    IF NEW.visits > 0 THEN
        NEW.ctr = ROUND((NEW.clicks::numeric / NEW.visits::numeric) * 100, 4);
    ELSE
        NEW.ctr = 0;
    END IF;

    -- Calcul du CPC
    IF NEW.clicks > 0 THEN
        NEW.cost_per_click = ROUND(NEW.budget / NEW.clicks, 4);
    ELSE
        NEW.cost_per_click = NULL;
    END IF;

    NEW.updated_at = CURRENT_TIMESTAMP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_calculate_hypeddit_metrics
BEFORE INSERT OR UPDATE ON hypeddit_daily_stats
FOR EACH ROW
EXECUTE FUNCTION calculate_hypeddit_metrics();
