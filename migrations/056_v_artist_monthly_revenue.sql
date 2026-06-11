-- 056_v_artist_monthly_revenue.sql
-- Single source of truth for an artist's monthly MUSIC revenue, unioning every revenue
-- source: iMusician + DistroKid (distributor monthly tables) + SACEM gross royalties
-- (REPARTITION lines of sacem_statement). Adding a future source = one UNION branch here
-- instead of editing the ~6 places that previously copy-pasted this UNION (get_roi_data,
-- get_monthly_roi_series, load_artist_revenues, load_artist_revenue_by_source, the LTV
-- avg query, _roi_data_span). Read-only → NOT registered in _ALLOWED_TABLES. Idempotent.

CREATE OR REPLACE VIEW v_artist_monthly_revenue AS
    SELECT artist_id, year, month, 'imusician'::text AS source, revenue_eur
        FROM imusician_monthly_revenue
    UNION ALL
    SELECT artist_id, year, month, 'distrokid'::text, revenue_eur
        FROM distrokid_monthly_revenue
    UNION ALL
    SELECT artist_id,
           EXTRACT(YEAR FROM line_date)::int  AS year,
           EXTRACT(MONTH FROM line_date)::int AS month,
           'sacem'::text, mouvement_eur AS revenue_eur
        FROM sacem_statement WHERE line_type = 'repartition';
