-- The one fingerprint every schema comparison uses. Extracted 2026-08-21.
--
-- It was inlined TWICE in the Makefile (canonical side and prod side) as one
-- unbroken line. Two copies of a comparison key are two things that drift, and a
-- drift here makes the comparison quietly compare the wrong thing — the exact
-- failure mode the check exists to catch.
--
-- Names, not types, on purpose: a type-level diff reports `text` vs
-- `character varying` as a difference when Postgres treats a VARCHAR with no
-- length AS text. Measured on this repo: 26 "type differences", 24 of them that
-- noise. A check that cries wolf gets skimmed, then ignored.
--
-- Constraints and unique indexes are included because a column-only diff once
-- called prod "identical" while its youtube_videos PRIMARY KEY sat on a
-- different column.
SELECT 'col:' || table_name || '.' || column_name
  FROM information_schema.columns WHERE table_schema = 'public'
UNION ALL
SELECT 'key:' || conrelid::regclass || ':' || pg_get_constraintdef(oid)
  FROM pg_constraint
 WHERE connamespace = 'public'::regnamespace AND contype IN ('p', 'u', 'f')
UNION ALL
SELECT 'uix:' || tablename || ':' || substring(indexdef from 'USING .*')
  FROM pg_indexes
 WHERE schemaname = 'public' AND indexdef LIKE 'CREATE UNIQUE%'
 ORDER BY 1;
