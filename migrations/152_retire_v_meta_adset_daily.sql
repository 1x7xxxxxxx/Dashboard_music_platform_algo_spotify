-- 152 — retire v_meta_adset_daily (R597).
--
-- Owner, 2026-10-15: the « Optimisation de l'ad set » panel of « Tes meilleurs réglages »
-- is gone (its question is the « Objectif » panel's). It was the view's only reader. A
-- gold view nothing reads is frozen work (`make gold-coverage`, « Objets or non lus »),
-- the same retirement as migration 151.
--
-- A view holds no data: `meta_insights` keeps every row, and migration 108 recreates
-- the view verbatim if a surface ever needs it again.
DROP VIEW IF EXISTS v_meta_adset_daily;
